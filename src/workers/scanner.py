"""Scanner : surveille le wallet watch-only par polling et alimente la base.

Il écrit `received_output` (sorties vues, confirmations) et met une ligne en file dans
`webhook_delivery` quand une sortie atteint le seuil de confirmations. Il n'envoie rien : l'envoi
(réessais, backoff) est dans `sender.py`, les deux ne communiquent que par la base.
"""
import asyncio
import time
from datetime import timedelta
from socket import gethostname
from uuid import uuid4

from aiohttp import ClientError
from prisma import Prisma
from prisma.errors import PrismaError

from chauff_cmn.logging import logger as log
from src.modules.bitcoin_cli.client import Client, RpcError
from src.utils.alerts import alert
from src.utils.money import btc_to_sats
from src.v1.services.derivation import AddressDeriver

from . import wallet as wallet_ops

# Plage d'adresses importée dans le wallet : étendue quand l'index le plus récent s'en approche
RANGE_SIZE = 1000
RANGE_MARGIN = 200
STALLED_AFTER_SECONDS = 600

_LEASE_SQL = """
INSERT INTO scan_cursor (id, lease_owner, lease_until)
VALUES (1, $1::text, now() + make_interval(secs => $2::double precision))
ON CONFLICT (id) DO UPDATE
SET lease_owner = $1::text, lease_until = now() + make_interval(secs => $2::double precision)
WHERE scan_cursor.lease_owner = $1::text OR scan_cursor.lease_until IS NULL OR scan_cursor.lease_until < now()
RETURNING last_block_hash
"""


class Scanner:
    def __init__(
        self,
        *,
        node: Client,
        wallet: Client,
        wallet_name: str,
        db: Prisma,
        deriver: AddressDeriver,
        min_confirmations: int,
        dust_sats: int,
        interval_seconds: float,
        owner: str | None = None,
    ):
        self._node = node
        self._wallet = wallet
        self._wallet_name = wallet_name
        self._db = db
        self._deriver = deriver
        self._min_confirmations = min_confirmations
        self._dust_sats = dust_sats
        self._interval = interval_seconds
        # Bail : deux instances ne scannent jamais en même temps (3 ticks pour reprendre après une panne)
        self._owner = owner or f"{gethostname()}-{uuid4().hex[:8]}"
        self._lease_seconds = max(3 * interval_seconds, 10)
        self._range_end = 0
        self._ready = False
        self._last_success = time.monotonic()

    # --- préparation du wallet -------------------------------------------------------------

    async def setup(self) -> None:
        await wallet_ops.ensure_wallet(self._node, self._wallet_name)
        descriptor = await self._deriver.get_descriptor()
        end = await wallet_ops.descriptor_range_end(self._wallet, descriptor)
        newest = await self._db.invoice.find_first(order={"derivationIndex": "desc"})
        wanted = (newest.derivationIndex if newest else 0) + RANGE_SIZE
        if end is None:
            oldest = await self._db.invoice.find_first(order={"createdAt": "asc"})
            await wallet_ops.import_range(self._wallet, descriptor, wanted, oldest.createdAt if oldest else None)
            end = await wallet_ops.descriptor_range_end(self._wallet, descriptor)
        self._range_end = end
        self._ready = True
        log.info("Scanner prêt (wallet {}, plage 0..{})", self._wallet_name, end)

    async def _extend_range(self) -> None:
        newest = await self._db.invoice.find_first(order={"derivationIndex": "desc"})
        if newest and newest.derivationIndex + RANGE_MARGIN > self._range_end:
            descriptor = await self._deriver.get_descriptor()
            # Bitcoin Core refuse de réduire une plage et l'étend lui-même de 1000 adresses après chaque usage :
            # on relit la plage réelle plutôt que de supposer la valeur demandée
            wanted = max(newest.derivationIndex + RANGE_SIZE, self._range_end + 1)
            # Adresses jamais émises au-delà de l'ancienne plage : rien à rattraper (pas de rescan)
            await wallet_ops.import_range(self._wallet, descriptor, wanted, None)
            self._range_end = await wallet_ops.descriptor_range_end(self._wallet, descriptor)
            log.info("Plage du wallet étendue à 0..{}", self._range_end)

    # --- un passage ------------------------------------------------------------------------

    async def tick(self) -> bool:
        """Un passage de scan. Faux si une autre instance tient le bail."""
        rows = await self._db.query_raw(_LEASE_SQL, self._owner, self._lease_seconds)
        if not rows:
            return False
        await self._extend_range()
        # Cible « seuil + 1 » : le curseur reste un bloc en arrière du seuil, donc une sortie est
        # toujours revue avec exactement `seuil` confirmations avant que le curseur ne la dépasse.
        result = await self._wallet.list_since_block(rows[0]["last_block_hash"], self._min_confirmations + 1)
        height = (await self._node.get_block_header(result["lastblock"]))["height"]
        await self._persist(result, height)
        return True

    async def _persist(self, result: dict, height: int) -> None:
        received = [t for t in result["transactions"] if self._is_receive(t)]
        removed = [t for t in result.get("removed", []) if self._is_receive(t)]
        addresses = list({t["address"] for t in received + removed})
        issued = (
            {i.address for i in await self._db.invoice.find_many(where={"address": {"in": addresses}})}
            if addresses
            else set()
        )
        for address in set(addresses) - issued:
            log.warning("Fonds reçus sur une adresse du wallet jamais émise : {}", address)

        async with self._db.tx(timeout=timedelta(seconds=30)) as tx:
            for entry in removed:
                if entry["address"] in issued:
                    await self._drop(tx, entry)
            for entry in received:
                if entry["address"] in issued:
                    await self._record(tx, entry)
            for address in {e["address"] for e in received if e["address"] in issued}:
                await self._flag_seen(tx, address)
            await tx.execute_raw(
                "UPDATE scan_cursor SET last_block_hash = $1::text, last_block_height = $2::int "
                "WHERE id = 1 AND lease_owner = $3::text",
                result["lastblock"],
                height,
                self._owner,
            )

    @staticmethod
    def _is_receive(entry: dict) -> bool:
        return entry.get("category") == "receive" and "vout" in entry and bool(entry.get("address"))

    async def _record(self, tx, entry: dict) -> None:
        key = {"txid_vout": {"txid": entry["txid"], "vout": entry["vout"]}}
        confirmations = entry.get("confirmations", 0)
        # Abandonnée ou en conflit (confirmations < 0) : comme si elle n'était plus dans la chaîne
        gone = bool(entry.get("abandoned")) or confirmations < 0
        confirmations = 0 if gone else confirmations
        position = {
            "confirmations": confirmations,
            "blockHeight": None if gone else entry.get("blockheight"),
            "blockHash": None if gone else entry.get("blockhash"),
        }
        sats = btc_to_sats(entry["amount"])
        existing = await tx.receivedoutput.find_unique(where=key, include={"invoice": True})
        if existing is None:
            await tx.receivedoutput.create(
                data={
                    "txid": entry["txid"],
                    "vout": entry["vout"],
                    "amountSats": sats,
                    "invoice": {"connect": {"address": entry["address"]}},
                    **position,
                }
            )
        else:
            await tx.receivedoutput.update(where=key, data=position)
            # Une sortie notifiée n'a plus que des confirmations croissantes : si elle retombe sous le seuil
            # (retirée de la chaîne, repassée en mempool, en conflit), c'est une réorganisation
            if existing.notifiedAt and confirmations < self._min_confirmations:
                self._alert_reorg(entry, existing.invoice.orderId)

        notified = existing is not None and existing.notifiedAt is not None
        if confirmations >= self._min_confirmations and sats > self._dust_sats and not notified:
            # Idempotent : une sortie n'est mise en file qu'une fois (replay : voir l'envoi)
            await tx.webhookdelivery.create_many(
                data=[{"txid": entry["txid"], "vout": entry["vout"]}], skip_duplicates=True
            )

    async def _flag_seen(self, tx, address: str) -> None:
        """Met en file l'avis « paiement complet vu » dès que les sorties vues couvrent le montant attendu.

        Compte aussi le mempool (0 confirmation) : c'est tout l'intérêt, le shop arrête le décompte de sa
        réservation sans attendre les confirmations. Une seule fois par facture.
        """
        invoice = await tx.invoice.find_unique(where={"address": address}, include={"outputs": True, "seenNotice": True})
        if invoice is None or invoice.seenNotice is not None:
            return
        outputs = [o for o in invoice.outputs or [] if o.amountSats > self._dust_sats]
        total = sum(o.amountSats for o in outputs)
        if not outputs or total < invoice.expectedSats:
            return
        last = max(outputs, key=lambda o: o.firstSeenAt)
        await tx.seennotice.create_many(
            data=[{"invoiceId": invoice.id, "txid": last.txid, "vout": last.vout, "totalSats": total}],
            skip_duplicates=True,
        )

    async def _drop(self, tx, entry: dict) -> None:
        """Transaction sortie de la chaîne par une réorganisation."""
        key = {"txid_vout": {"txid": entry["txid"], "vout": entry["vout"]}}
        existing = await tx.receivedoutput.find_unique(where=key, include={"invoice": True})
        if existing is None:
            return
        await tx.receivedoutput.update(where=key, data={"confirmations": 0, "blockHeight": None, "blockHash": None})
        if existing.notifiedAt:
            self._alert_reorg(entry, existing.invoice.orderId)

    @staticmethod
    def _alert_reorg(entry: dict, order_id: str) -> None:
        alert(
            "reorg_after_notification",
            "Sortie déjà notifiée au shop retirée de la chaîne : traitement manuel",
            txid=entry["txid"],
            vout=entry["vout"],
            order_id=order_id,
        )

    # --- boucle ----------------------------------------------------------------------------

    async def run(self) -> None:
        while True:
            try:
                if not self._ready:
                    await self.setup()
                await self.tick()
                self._last_success = time.monotonic()
            except asyncio.CancelledError:
                raise
            except (RpcError, ClientError, OSError) as exc:
                alert("node_unreachable", "Nœud Bitcoin injoignable ou en erreur", level="WARNING", error=str(exc))
            except PrismaError as exc:
                alert("db_unavailable", "Base de données indisponible (scanner)", level="WARNING", error=str(exc))
            except Exception:
                log.exception("Erreur inattendue du scanner")
            if time.monotonic() - self._last_success > STALLED_AFTER_SECONDS:
                alert("scanner_stalled", "Le scanner n'avance plus", seconds=int(time.monotonic() - self._last_success))
            await asyncio.sleep(self._interval)
