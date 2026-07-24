from unittest.mock import AsyncMock, patch

import pytest
import pytest_asyncio
from aiohttp import web
from aiohttp.test_utils import TestClient, TestServer

from src.v1 import handlers
from src.v1.app import routes


@pytest_asyncio.fixture
async def api_client():
    app = web.Application()
    app.add_routes(routes)
    server = TestServer(app)
    client = TestClient(server)
    await client.start_server()
    try:
        yield client
    finally:
        await client.close()


@pytest.mark.asyncio
async def test_get_price_route_returns_json(api_client: TestClient):
    with patch.object(handlers.market.market, "get_price", AsyncMock(return_value={"USD": 100_000})):
        response = await api_client.get("/bitcoin-price")
        assert response.status == 200
        assert await response.json() == {"USD": 100000}


@pytest.mark.asyncio
async def test_get_height_route_returns_json(api_client: TestClient):
    with patch.object(handlers.onchain.onchain, "get_block_height", AsyncMock(return_value=900_000)):
        response = await api_client.get("/bitcoin-block-height")
        assert response.status == 200
        assert await response.json() == 900000


@pytest.mark.asyncio
async def test_get_difficulty_route_returns_json(api_client: TestClient):
    with patch.object(handlers.onchain.onchain, "get_difficulty", AsyncMock(return_value=123.45)):
        response = await api_client.get("/bitcoin-blockchain-difficulty")
        assert response.status == 200
        assert await response.json() == 123.45


@pytest.mark.asyncio
async def test_get_difficulty_route_returns_500_on_internal_error(api_client: TestClient):
    with patch.object(handlers.onchain.onchain, "get_difficulty", AsyncMock(side_effect=RuntimeError("boom"))):
        response = await api_client.get("/bitcoin-blockchain-difficulty")
        assert response.status == 500
