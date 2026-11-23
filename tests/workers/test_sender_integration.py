"""Envoi du webhook contre un vrai Postgres (testcontainers) et un faux shop HTTP."""
import asyncio
from datetime import datetime, timedelta, timezone

import pytest
import pytest_asyncio
from aiohttp import web
from aiohttp.test_utils import TestServer
from chauff_cmn.logging import logger as log
from prisma import Prisma

from src.v1.services import deliveries, invoices
from src.workers.sender import Sender

SECRET = "shop-secret-0123456789abcdef0123456789"


class FakeShop:
    """Répond avec la file de statuts donnée, puis avec `default`, et garde ce qu'il reçoit."""

    def __init__(self):
        self.statuses: list[int] = []
        self.default = 201
        self.delay = 0.0
        self.received: list[dict] = []

    async def handle(self, request: web.Request):
        self.received.append({"auth": request.headers.get("Authorization"), "body": await request.json()})
        if self.delay:
            await asyncio.sleep(self.delay)
        status = self.statuses.pop(0) if self.statuses else self.default
        return web.json_response({"ok": status < 300}, status=status)


@pytest_asyncio.fixture
async def env(monkeypatch, postgres_url):
    shop = FakeShop()
    app = web.Application()
    app.router.add_post("/api/internal/payments", shop.handle)
    server = TestServer(app)
    await server.start_server()

    db = Prisma(datasource={"url": postgres_url})
    await db.connect()
    await db.execute_raw('TRUNCATE "webhook_delivery", "received_output", "invoice", "scan_cursor" CASCADE')

    def make_sender(**kwargs):
        return Sender(
            db=db,
            url=str(server.make_url("/api/internal/payments")),
            secret=SECRET,
            min_confirmations=3,
            interval_seconds=1,
            **kwargs,
        )

    async def make_delivery(order_id="o1", sats=150_000, confirmations=3):
        class Deriver:
            async def address(self, index):
                return f"bcrt1qtest{index:06d}"

        async def price():
            return 9_000_000

        monkeypatch.setattr(invoices, "get_deriver", lambda: Deriver())
        monkeypatch.setattr(invoices, "get_btc_price_eur_cents", price)
        invoice, _ = await invoices.create_invoice(order_id, 119_000, db)
        txid = f"{abs(hash(order_id)):064x}"[:64]
        await db.receivedoutput.create(
            data={
                "txid": txid,
                "vout": 1,
                "amountSats": sats,
                "confirmations": confirmations,
                "invoice": {"connect": {"address": invoice.address}},
            }
        )
        await db.webhookdelivery.create(data={"txid": txid, "vout": 1})
        return invoice, txid

    async def due_now():
        await db.execute_raw('UPDATE "webhook_delivery" SET "next_attempt_at" = now() - interval \'1 second\'')

    records = []
    sink = log.add(lambda m: records.append(m.record), level="WARNING")
    env = type("Env", (), {})()
    env.shop, env.db, env.make_sender, env.make_delivery, env.due_now = shop, db, make_sender, make_delivery, due_now
    env.alerts = lambda: [(r["level"].name, r["extra"]["alert_name"]) for r in records if r["extra"].get("alert")]
    try:
        yield env
    finally:
        log.remove(sink)
        await db.disconnect()
        await server.close()


async def _delivery(env):
    return await env.db.webhookdelivery.find_first()


@pytest.mark.asyncio
async def test_delivers_with_exact_payload_and_marks_notified(env):
    invoice, txid = await env.make_delivery()
    sender = env.make_sender()

    assert await sender.tick() == 1

    assert env.shop.received == [
        {
            "auth": f"Bearer {SECRET}",
            "body": {"address": invoice.address, "txid": txid, "vout": 1, "amountSats": "150000"},
        }
    ]
    delivery = await _delivery(env)
    assert (delivery.attempts, delivery.lastStatusCode) == (1, 201)
    assert delivery.deliveredAt is not None
    assert (await env.db.receivedoutput.find_first()).notifiedAt is not None
    # Rien à renvoyer au passage suivant
    assert await sender.tick() == 0


@pytest.mark.asyncio
async def test_retries_with_backoff_then_delivers(env):
    await env.make_delivery()
    env.shop.statuses = [503, 503]
    sender = env.make_sender()

    await sender.tick()
    delivery = await _delivery(env)
    assert (delivery.attempts, delivery.lastStatusCode, delivery.deliveredAt) == (1, 503, None)
    assert delivery.nextAttemptAt > datetime.now(timezone.utc) + timedelta(seconds=3)  # ~5 s ± 20 %
    assert await sender.tick() == 0  # pas encore dû

    await env.due_now()
    await sender.tick()
    delivery = await _delivery(env)
    assert delivery.attempts == 2 and delivery.nextAttemptAt > datetime.now(timezone.utc) + timedelta(seconds=10)  # ~15 s

    await env.due_now()
    await sender.tick()
    delivery = await _delivery(env)
    assert delivery.attempts == 3 and delivery.deliveredAt is not None
    assert len(env.shop.received) == 3


@pytest.mark.asyncio
@pytest.mark.parametrize("status", [400, 401, 409])
async def test_rejection_is_final_and_alerts(env, status):
    await env.make_delivery()
    env.shop.default = status
    sender = env.make_sender()

    await sender.tick()

    delivery = await _delivery(env)
    assert (delivery.failReason, delivery.lastStatusCode) == ("rejected", status)
    assert delivery.failedAt is not None
    assert ("ERROR", "webhook_rejected") in env.alerts()
    await env.due_now()
    assert await sender.tick() == 0
    assert len(env.shop.received) == 1
    assert (await env.db.receivedoutput.find_first()).notifiedAt is None


@pytest.mark.asyncio
async def test_unknown_address_is_retried_quietly_then_loudly(env):
    await env.make_delivery()
    env.shop.default = 404
    sender = env.make_sender()

    await sender.tick()
    assert (await _delivery(env)).failedAt is None
    assert env.alerts() == [("WARNING", "webhook_unknown_address")]

    # Plus d'une heure plus tard : l'anomalie devient une erreur
    await env.db.execute_raw("UPDATE \"webhook_delivery\" SET \"created_at\" = now() - interval '2 hours'")
    await env.due_now()
    await sender.tick()
    assert ("ERROR", "webhook_unknown_address") in env.alerts()
    assert (await _delivery(env)).failedAt is None


@pytest.mark.asyncio
async def test_gives_up_after_72_hours(env):
    await env.make_delivery()
    env.shop.default = 503
    await env.db.execute_raw("UPDATE \"webhook_delivery\" SET \"created_at\" = now() - interval '73 hours'")
    sender = env.make_sender()

    await sender.tick()

    delivery = await _delivery(env)
    assert (delivery.failReason, delivery.attempts) == ("expired", 1)
    assert ("ERROR", "webhook_failed_permanently") in env.alerts()


@pytest.mark.asyncio
async def test_timeout_is_retried(env):
    await env.make_delivery()
    env.shop.delay = 1.5
    sender = env.make_sender(timeout_seconds=0.3)

    await sender.tick()

    delivery = await _delivery(env)
    assert delivery.attempts == 1 and delivery.deliveredAt is None and delivery.failedAt is None
    assert delivery.lastError and "Timeout" in delivery.lastError


@pytest.mark.asyncio
async def test_two_senders_never_send_the_same_delivery_twice(env):
    await env.make_delivery()
    env.shop.delay = 0.3  # laisse le temps à l'autre instance d'essayer
    first, second = env.make_sender(), env.make_sender()

    await asyncio.gather(first.tick(), second.tick())

    assert len(env.shop.received) == 1


@pytest.mark.asyncio
async def test_output_below_threshold_is_held_not_sent(env):
    await env.make_delivery(confirmations=0)  # sortie retirée de la chaîne depuis la mise en file
    sender = env.make_sender()

    await sender.tick()

    assert env.shop.received == []
    delivery = await _delivery(env)
    assert delivery.attempts == 0 and delivery.nextAttemptAt > datetime.now(timezone.utc) + timedelta(seconds=30)


@pytest.mark.asyncio
async def test_replay_restarts_a_delivered_and_a_failed_delivery(env):
    await env.make_delivery("o1")
    sender = env.make_sender()
    await sender.tick()
    assert (await _delivery(env)).deliveredAt is not None

    assert await deliveries.replay_invoice("o1", env.db) == 1

    delivery = await _delivery(env)
    assert (delivery.attempts, delivery.deliveredAt, delivery.failedAt) == (0, None, None)
    await sender.tick()
    assert len(env.shop.received) == 2 and (await _delivery(env)).deliveredAt is not None


@pytest.mark.asyncio
async def test_replay_skips_dust_and_unconfirmed(env):
    await env.make_delivery("dust", sats=500)
    await env.make_delivery("young", confirmations=1)
    await env.db.webhookdelivery.delete_many()

    assert await deliveries.replay_invoice("dust", env.db) == 0
    assert await deliveries.replay_invoice("young", env.db) == 0
    assert await env.db.webhookdelivery.count() == 0
