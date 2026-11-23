"""Création de factures sur un vrai Postgres (testcontainers, migrations appliquées).

Les tables sont vidées avant chaque test ; la séquence est conservée (un index n'est jamais rejoué).
"""
import asyncio
import pytest
import pytest_asyncio
from prisma import Prisma

from src.v1.errors import ApiError
from src.v1.services import invoices


class FakeDeriver:
    async def address(self, index: int) -> str:
        await asyncio.sleep(0.01)  # laisse les appels simultanés s'entrecroiser
        return f"bcrt1qtest{index:06d}"


@pytest_asyncio.fixture
async def client(monkeypatch, postgres_url):
    client = Prisma(datasource={"url": postgres_url})
    await client.connect()
    await client.execute_raw('TRUNCATE "webhook_delivery", "received_output", "invoice", "scan_cursor" CASCADE')
    monkeypatch.setattr(invoices, "get_deriver", lambda: FakeDeriver())

    async def price():
        return 9_000_000

    monkeypatch.setattr(invoices, "get_btc_price_eur_cents", price)
    try:
        yield client
    finally:
        await client.disconnect()


@pytest.mark.asyncio
async def test_create_is_idempotent_on_order_id(client):
    first, created = await invoices.create_invoice("order-1", 119_000, client)
    again, created_again = await invoices.create_invoice("order-1", 119_000, client)

    assert (created, created_again) == (True, False)
    assert again.address == first.address
    assert again.expectedSats == first.expectedSats == 1_322_223
    assert await client.invoice.count() == 1


@pytest.mark.asyncio
async def test_same_order_with_other_amount_conflicts(client):
    await invoices.create_invoice("order-1", 119_000, client)
    with pytest.raises(ApiError) as exc:
        await invoices.create_invoice("order-1", 5_000, client)
    assert (exc.value.status, exc.value.code) == (409, "invoice_conflict")


@pytest.mark.asyncio
async def test_each_order_gets_its_own_address_and_index(client):
    results = [await invoices.create_invoice(f"order-{i}", 1_000, client) for i in range(5)]
    invoices_ = [invoice for invoice, _ in results]

    assert len({i.address for i in invoices_}) == 5
    assert len({i.derivationIndex for i in invoices_}) == 5


@pytest.mark.asyncio
async def test_concurrent_calls_for_one_order_return_one_invoice(client):
    results = await asyncio.gather(*[invoices.create_invoice("order-race", 50_000, client) for _ in range(8)])

    assert len({invoice.address for invoice, _ in results}) == 1
    assert sum(1 for _, created in results if created) == 1
    assert await client.invoice.count() == 1


@pytest.mark.asyncio
async def test_get_invoice_and_unknown(client):
    await invoices.create_invoice("order-1", 1_000, client)

    assert (await invoices.get_invoice("order-1", client)).outputs == []
    with pytest.raises(ApiError) as exc:
        await invoices.get_invoice("unknown", client)
    assert exc.value.status == 404
