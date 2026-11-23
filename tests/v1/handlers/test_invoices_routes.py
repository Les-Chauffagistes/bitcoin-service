from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest
import pytest_asyncio
from aiohttp import web
from aiohttp.test_utils import TestClient, TestServer

from src.settings import settings
from src.v1 import handlers
from src.v1.app import routes
from src.v1.errors import ApiError

HEADERS = {"X-Api-Key": settings.api_token}
ORDER_ID = "2f6b1c1e-9a43-4c53-8b52-1f6f4a0f9d11"


def _invoice():
    return SimpleNamespace(
        orderId=ORDER_ID,
        address="bc1qaddress",
        amountCents=119_000,
        expectedSats=1_322_223,
        btcPriceEurCents=9_000_000,
        createdAt=datetime(2026, 11, 23, tzinfo=timezone.utc),
        outputs=[],
    )


@pytest_asyncio.fixture
async def api_client():
    app = web.Application()
    app.add_routes(routes)
    client = TestClient(TestServer(app))
    await client.start_server()
    try:
        yield client
    finally:
        await client.close()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("method", "path"),
    [
        ("post", "/invoices"),
        ("get", f"/invoices/{ORDER_ID}"),
        ("post", f"/invoices/{ORDER_ID}/replay"),
        ("get", "/fee-estimate"),
    ],
)
async def test_routes_require_api_key(api_client: TestClient, method, path):
    assert (await getattr(api_client, method)(path)).status == 401
    assert (await getattr(api_client, method)(path, headers={"X-Api-Key": "wrong"})).status == 401


@pytest.mark.asyncio
async def test_create_returns_201_with_strings(api_client: TestClient):
    create = AsyncMock(return_value=(_invoice(), True))
    with patch.object(handlers.invoices.invoices, "create_invoice", create):
        response = await api_client.post(
            "/invoices", json={"orderId": ORDER_ID, "amountCents": "119000"}, headers=HEADERS
        )

    assert response.status == 201
    assert await response.json() == {"address": "bc1qaddress", "expectedSats": "1322223", "btcPriceEurCents": "9000000"}
    create.assert_awaited_once_with(ORDER_ID, 119_000)


@pytest.mark.asyncio
async def test_create_existing_returns_200(api_client: TestClient):
    with patch.object(handlers.invoices.invoices, "create_invoice", AsyncMock(return_value=(_invoice(), False))):
        response = await api_client.post(
            "/invoices", json={"orderId": ORDER_ID, "amountCents": "119000"}, headers=HEADERS
        )
    assert response.status == 200


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "body",
    [
        {},
        {"orderId": ORDER_ID},
        {"orderId": ORDER_ID, "amountCents": 119000},  # nombre, pas une chaîne
        {"orderId": ORDER_ID, "amountCents": "0"},
        {"orderId": ORDER_ID, "amountCents": "-5"},
        {"orderId": ORDER_ID, "amountCents": "12.5"},
        {"orderId": ORDER_ID, "amountCents": "1" * 19},
        {"orderId": "", "amountCents": "100"},
        {"orderId": "a b", "amountCents": "100"},
        {"orderId": ORDER_ID, "amountCents": "100", "extra": 1},
        [],
    ],
)
async def test_create_rejects_invalid_payload(api_client: TestClient, body):
    create = AsyncMock()
    with patch.object(handlers.invoices.invoices, "create_invoice", create):
        response = await api_client.post("/invoices", json=body, headers=HEADERS)

    assert response.status == 400
    assert (await response.json())["error"] == "invalid_payload"
    create.assert_not_awaited()


@pytest.mark.asyncio
async def test_create_rejects_non_json(api_client: TestClient):
    response = await api_client.post("/invoices", data="nope", headers=HEADERS)
    assert response.status == 400


@pytest.mark.asyncio
async def test_create_maps_api_errors(api_client: TestClient):
    error = ApiError(409, "invoice_conflict", "Cette facture existe déjà avec un autre montant.")
    with patch.object(handlers.invoices.invoices, "create_invoice", AsyncMock(side_effect=error)):
        response = await api_client.post(
            "/invoices", json={"orderId": ORDER_ID, "amountCents": "5"}, headers=HEADERS
        )
    assert response.status == 409
    assert (await response.json())["error"] == "invoice_conflict"


@pytest.mark.asyncio
async def test_get_unknown_invoice_is_404(api_client: TestClient):
    error = ApiError(404, "invoice_not_found", "Facture introuvable.")
    with patch.object(handlers.invoices.invoices, "get_invoice", AsyncMock(side_effect=error)):
        response = await api_client.get("/invoices/unknown", headers=HEADERS)
    assert response.status == 404


@pytest.mark.asyncio
async def test_get_invoice_lists_outputs(api_client: TestClient):
    invoice = _invoice()
    invoice.outputs = [
        SimpleNamespace(txid="ab" * 32, vout=1, amountSats=150_000, confirmations=2, blockHeight=800_000, notifiedAt=None)
    ]
    with patch.object(handlers.invoices.invoices, "get_invoice", AsyncMock(return_value=invoice)):
        response = await api_client.get(f"/invoices/{ORDER_ID}", headers=HEADERS)

    body = await response.json()
    assert response.status == 200
    assert body["amountCents"] == "119000"
    assert body["outputs"] == [
        {"txid": "ab" * 32, "vout": 1, "amountSats": "150000", "confirmations": 2, "blockHeight": 800_000, "notifiedAt": None}
    ]


@pytest.mark.asyncio
async def test_fee_estimate(api_client: TestClient):
    with patch.object(handlers.fees.fees, "get_refund_fee_sats", AsyncMock(return_value=1_410)):
        response = await api_client.get("/fee-estimate", headers=HEADERS)
    assert await response.json() == {"refundNetworkFeeSats": "1410"}


@pytest.mark.asyncio
async def test_replay_returns_queued_count(api_client: TestClient):
    with patch.object(handlers.invoices.deliveries, "replay_invoice", AsyncMock(return_value=2)) as replay:
        response = await api_client.post(f"/invoices/{ORDER_ID}/replay", headers=HEADERS)
    assert await response.json() == {"queued": 2}
    replay.assert_awaited_once_with(ORDER_ID)


@pytest.mark.asyncio
async def test_replay_unknown_invoice_is_404(api_client: TestClient):
    error = ApiError(404, "invoice_not_found", "Facture introuvable.")
    with patch.object(handlers.invoices.deliveries, "replay_invoice", AsyncMock(side_effect=error)):
        response = await api_client.post("/invoices/unknown/replay", headers=HEADERS)
    assert response.status == 404
