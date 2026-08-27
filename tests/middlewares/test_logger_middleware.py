from aiohttp import web
from aiohttp.test_utils import make_mocked_request
from aiohttp.web_exceptions import HTTPBadRequest
import pytest

from src.middlewares.logger import error_handler


class DummyLog:
    def __init__(self):
        self.calls = []
        self.error_called = False

    def info(self, *content):
        self.calls.append(("INFO", *content))

    def exception(self, *_):
        self.error_called = True


@pytest.mark.asyncio
async def test_error_handler_logs_success(monkeypatch):
    dummy = DummyLog()
    import init as hs_init

    monkeypatch.setattr(hs_init, "log", dummy)
    request = make_mocked_request("GET", "/health")

    async def ok_handler(_):
        return web.Response(status=201)

    response = await error_handler(request, ok_handler)

    assert response.status == 201
    assert dummy.calls == [("INFO", "GET /health 201")]


@pytest.mark.asyncio
async def test_error_handler_logs_http_exception_and_reraises(monkeypatch):
    dummy = DummyLog()
    import init as hs_init

    monkeypatch.setattr(hs_init, "log", dummy)
    request = make_mocked_request("POST", "/v1/bitcoin-price")

    async def failing_handler(_):
        raise HTTPBadRequest(text="bad")

    with pytest.raises(HTTPBadRequest):
        await error_handler(request, failing_handler)

    assert dummy.calls == [("INFO", "POST /v1/bitcoin-price 400")]
    assert dummy.error_called is True
