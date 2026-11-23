"""Scanner contre un vrai Postgres et un vrai bitcoind en regtest (testcontainers, voir conftest.py)."""
import uuid
from datetime import datetime, timezone

import pytest
import pytest_asyncio
from chauff_cmn.logging import logger as log
from prisma import Prisma

from src.modules.bitcoin_cli.client import Client, RpcError
from src.modules.xpub import _CANONICAL, _b58decode_check, _b58encode_check
from src.v1.services import invoices
from src.v1.services.derivation import AddressDeriver
from src.workers import wallet as wallet_ops
from src.workers.scanner import Scanner

BIP84_XPUB = "xpub6CatWdiZiodmUeTDp8LT5or8nmbKNcuyvz7WyksVFkKB4RHwCD3XyuvPEbvqAQY3rAPshWcMLoP2fMFMKHPJ4ZeZXYVUhLv1VMrjPC7PW6V"
TPUB = _b58encode_check(_CANONICAL["regtest"] + _b58decode_check(BIP84_XPUB)[4:])


class Chain:
    """Nœud regtest : un wallet qui mine et paie, et de quoi avancer les blocs."""

    def __init__(self, host, port, user, password):
        self.node = Client(host, port, user, password)
        self.miner = Client(host, port, user, password, wallet="miner-it")
        self._args = (host, port, user, password)

    async def start(self):
        try:
            await self.node.load_wallet("miner-it")
        except RpcError:
            try:
                await self.node._call("createwallet", ["miner-it"])
            except RpcError:
                pass  # déjà chargé
        if float(await self.miner._call("getbalance")) < 5:
            await self.mine(101)

    async def sync(self):
        # Les wallets sont notifiés de façon asynchrone par le nœud : attendre que la file soit vidée
        await self.node._call("syncwithvalidationinterfacequeue")

    async def mine(self, count: int) -> list[str]:
        address = await self.miner._call("getnewaddress")
        hashes = await self.node._call("generatetoaddress", [count, address])
        await self.sync()
        return hashes

    async def pay(self, address: str, btc: str) -> str:
        txid = await self.miner._call("sendtoaddress", [address, btc])
        await self.sync()
        return txid

    async def close(self):
        for client in (self.node, self.miner):
            if client._session:
                await client._session.close()


@pytest_asyncio.fixture
async def env(monkeypatch, postgres_url, bitcoind):
    host, port, user, password = bitcoind.host, bitcoind.port, bitcoind.user, bitcoind.password
    chain = Chain(host, port, user, password)
    await chain.start()

    db = Prisma(datasource={"url": postgres_url})
    await db.connect()
    # Pas de RESTART IDENTITY : comme en production un index n'est jamais rejoué, sinon une adresse déjà
    # payée lors d'un test précédent (la chaîne regtest persiste) serait retrouvée par le rescan.
    await db.execute_raw('TRUNCATE "seen_notice", "webhook_delivery", "received_output", "invoice", "scan_cursor" CASCADE')

    name = f"scan-{uuid.uuid4().hex[:8]}"
    wallet = Client(host, port, user, password, wallet=name)
    deriver = AddressDeriver(chain.node, TPUB, "regtest")
    monkeypatch.setattr(invoices, "get_deriver", lambda: deriver)

    async def price():
        return 9_000_000

    monkeypatch.setattr(invoices, "get_btc_price_eur_cents", price)

    def make_scanner(owner="a", **kwargs):
        return Scanner(
            node=chain.node,
            wallet=wallet,
            wallet_name=name,
            db=db,
            deriver=deriver,
            min_confirmations=3,
            dust_sats=1_000,
            interval_seconds=1,
            owner=owner,
            **kwargs,
        )

    env = type("Env", (), {})()
    env.chain, env.db, env.wallet, env.make_scanner = chain, db, wallet, make_scanner
    try:
        yield env
    finally:
        await db.disconnect()
        if wallet._session:
            await wallet._session.close()
        await chain.close()


async def _deliveries(db):
    return await db.webhookdelivery.find_many()


@pytest.mark.asyncio
async def test_delivery_queued_only_at_three_confirmations(env):
    invoice, _ = await invoices.create_invoice("o1", 119_000, env.db)
    scanner = env.make_scanner()
    await scanner.setup()

    txid = await env.chain.pay(invoice.address, "0.0015")
    await scanner.tick()
    [output] = await env.db.receivedoutput.find_many()
    assert (output.txid, output.amountSats, output.confirmations) == (txid, 150_000, 0)

    for expected in (1, 2):
        await env.chain.mine(1)
        await scanner.tick()
        assert (await env.db.receivedoutput.find_first()).confirmations == expected
        assert await _deliveries(env.db) == []

    await env.chain.mine(1)
    await scanner.tick()
    [delivery] = await _deliveries(env.db)
    assert (delivery.txid, delivery.attempts, delivery.deliveredAt) == (txid, 0, None)

    # Les passages suivants ne remettent rien en file, même quand le curseur dépasse la sortie
    for _ in range(3):
        await env.chain.mine(3)
        await scanner.tick()
    assert len(await _deliveries(env.db)) == 1
    assert (await env.db.scancursor.find_unique(where={"id": 1})).lastBlockHash is not None


@pytest.mark.asyncio
async def test_dust_is_recorded_but_never_queued(env):
    invoice, _ = await invoices.create_invoice("o-dust", 100, env.db)
    scanner = env.make_scanner()
    await scanner.setup()

    await env.chain.pay(invoice.address, "0.00000600")
    await env.chain.mine(4)
    await scanner.tick()

    assert (await env.db.receivedoutput.find_first()).amountSats == 600
    assert await _deliveries(env.db) == []


@pytest.mark.asyncio
async def test_two_outputs_on_one_address_give_two_deliveries(env):
    invoice, _ = await invoices.create_invoice("o2", 119_000, env.db)
    scanner = env.make_scanner()
    await scanner.setup()

    await env.chain.pay(invoice.address, "0.001")
    await env.chain.pay(invoice.address, "0.002")
    await env.chain.mine(3)
    await scanner.tick()

    assert sorted(o.amountSats for o in await env.db.receivedoutput.find_many()) == [100_000, 200_000]
    assert len(await _deliveries(env.db)) == 2


@pytest.mark.asyncio
async def test_only_the_lease_holder_scans(env):
    first, second = env.make_scanner("a"), env.make_scanner("b")
    await first.setup()

    assert await first.tick() is True
    assert await second.tick() is False
    assert await first.tick() is True  # le détenteur renouvelle son bail


@pytest.mark.asyncio
async def test_restart_catches_up_on_payments_made_while_down(env):
    invoice, _ = await invoices.create_invoice("o3", 119_000, env.db)
    await env.make_scanner().setup()

    await env.chain.pay(invoice.address, "0.0015")
    await env.chain.mine(8)  # aucun passage pendant ce temps

    restarted = env.make_scanner()  # nouvelle instance, même propriétaire du bail
    await restarted.setup()
    await restarted.tick()

    assert len(await _deliveries(env.db)) == 1


@pytest.mark.asyncio
async def test_range_is_extended_when_indexes_approach_its_end(env, monkeypatch):
    from src.workers import scanner as scanner_module

    scanner = env.make_scanner()
    await scanner.setup()
    before = scanner._range_end
    assert before >= 1000

    # Marge démesurée : le dernier index émis est « trop près » de la fin de la plage
    monkeypatch.setattr(scanner_module, "RANGE_MARGIN", before + 10_000)
    await invoices.create_invoice("r1", 1_000, env.db)
    await scanner.tick()

    descriptor = await scanner._deriver.get_descriptor()
    after = await wallet_ops.descriptor_range_end(env.wallet, descriptor)
    assert after > before
    assert scanner._range_end == after


@pytest.mark.asyncio
async def test_reorg_after_notification_raises_an_alert(env):
    invoice, _ = await invoices.create_invoice("o4", 119_000, env.db)
    scanner = env.make_scanner()
    await scanner.setup()

    await env.chain.pay(invoice.address, "0.0015")
    blocks = await env.chain.mine(3)
    await scanner.tick()
    await env.db.receivedoutput.update_many(where={}, data={"notifiedAt": datetime.now(timezone.utc)})

    records = []
    sink = log.add(lambda m: records.append(m.record), level="WARNING")
    try:
        await env.chain.node._call("invalidateblock", [blocks[0]])  # le bloc qui contient le paiement
        await scanner.tick()
    finally:
        log.remove(sink)
        await env.chain.node._call("reconsiderblock", [blocks[0]])

    alerts = [r["extra"] for r in records if r["extra"].get("alert_name") == "reorg_after_notification"]
    assert alerts and alerts[0]["order_id"] == "o4"
    assert (await env.db.receivedoutput.find_first()).confirmations == 0


@pytest.mark.asyncio
async def test_seen_notice_queued_when_mempool_covers_the_expected_amount(env):
    # 119 000 centimes à 90 000 € le BTC = 1 322 223 sats attendus
    invoice, _ = await invoices.create_invoice("o-seen", 119_000, env.db)
    assert invoice.expectedSats == 1_322_223
    scanner = env.make_scanner()
    await scanner.setup()

    # Paiement partiel vu : rien
    await env.chain.pay(invoice.address, "0.0100")
    await scanner.tick()
    assert await env.db.seennotice.find_many() == []

    # Le complément, encore dans le mempool (0 confirmation) : avis en file, pas de webhook de confirmation
    txid = await env.chain.pay(invoice.address, "0.0040")
    await scanner.tick()
    [notice] = await env.db.seennotice.find_many()
    assert (notice.invoiceId, notice.txid, notice.totalSats) == (invoice.id, txid, 1_400_000)
    assert await _deliveries(env.db) == []

    # Une seule fois par facture, même après de nouveaux passages et paiements
    await env.chain.pay(invoice.address, "0.0010")
    await scanner.tick()
    assert len(await env.db.seennotice.find_many()) == 1


@pytest.mark.asyncio
async def test_seen_notice_ignores_dust_and_unissued_addresses(env):
    invoice, _ = await invoices.create_invoice("o-seen-dust", 100, env.db)
    scanner = env.make_scanner()
    await scanner.setup()
    await env.chain.pay(invoice.address, "0.00000600")
    await scanner.tick()
    assert await env.db.seennotice.find_many() == []
