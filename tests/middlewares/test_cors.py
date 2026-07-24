from aiohttp import web
from aiohttp.test_utils import make_mocked_request
import pytest

from src.middlewares.cors import cors_middleware


@pytest.mark.asyncio
async def test_cors_adds_headers_for_allowed_origin():
    request = make_mocked_request(
        "GET",
        "/v1/bitcoin-price",
        headers={"Origin": "https://heatboard.chauffagistes-btc.fr"},
    )

    async def handler(_):
        return web.json_response({"ok": True})

    response = await cors_middleware(request, handler)

    assert response.status == 200
    assert response.headers["Access-Control-Allow-Origin"] == "https://heatboard.chauffagistes-btc.fr"
    assert response.headers["Access-Control-Allow-Credentials"] == "true"


@pytest.mark.asyncio
async def test_cors_does_not_add_headers_for_unknown_origin():
    request = make_mocked_request("GET", "/v1/bitcoin-price", headers={"Origin": "https://evil.example"})

    async def handler(_):
        return web.json_response({"ok": True})

    response = await cors_middleware(request, handler)

    assert response.status == 200
    assert "Access-Control-Allow-Origin" not in response.headers


@pytest.mark.asyncio
async def test_cors_options_returns_204():
    request = make_mocked_request(
        "OPTIONS",
        "/v1/bitcoin-price",
        headers={"Origin": "https://contenders.chauffagistes-btc.fr"},
    )

    async def handler(_):
        raise AssertionError("handler must not be called for OPTIONS")

    response = await cors_middleware(request, handler)

    assert response.status == 204
    assert response.headers["Access-Control-Allow-Origin"] == "https://contenders.chauffagistes-btc.fr"
