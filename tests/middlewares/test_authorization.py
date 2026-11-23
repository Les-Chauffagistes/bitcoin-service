import pytest
from aiohttp import web
from aiohttp.test_utils import make_mocked_request

from src.middlewares.authorization import require_auth
from src.settings import settings


@require_auth
async def _handler(_: web.Request) -> web.Response:
    return web.Response(text="ok")


@pytest.mark.asyncio
async def test_accepts_valid_token():
    request = make_mocked_request("GET", "/", headers={"X-Api-Key": settings.api_token})
    response = await _handler(request)
    assert response.status == 200


@pytest.mark.asyncio
@pytest.mark.parametrize("headers", [{}, {"X-Api-Key": ""}, {"X-Api-Key": "wrong"}, {"X-Api-Key": "é" * 40}])
async def test_rejects_missing_or_invalid_token(headers):
    request = make_mocked_request("GET", "/", headers=headers)
    with pytest.raises(web.HTTPUnauthorized):
        await _handler(request)
