from aiohttp import web
from aiohttp.test_utils import make_mocked_request
from aiohttp.web_exceptions import HTTPBadRequest
import pytest

from src.middlewares.logger import error_handler


class DummyLine:
    def __init__(self):
        self.entries = []
        self.edited = False

    def add_text(self, *content):
        self.entries.extend(content)

    def edit_print(self):
        self.edited = True


class DummyLog:
    def __init__(self):
        self.line = DummyLine()
        self.error_called = False
        self.called = []

    def get(self, path):
        self.called.append(("GET", path))
        return self.line

    def post(self, path):
        self.called.append(("POST", path))
        return self.line

    def delete(self, path):
        self.called.append(("DELETE", path))
        return self.line

    def info(self, path):
        self.called.append(("INFO", path))
        return self.line

    def error(self, *_):
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
    assert ("GET", "/health") in dummy.called
    assert "HTTP" in dummy.line.entries
    assert 201 in dummy.line.entries
    assert dummy.line.edited is True


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

    assert ("POST", "/v1/bitcoin-price") in dummy.called
    assert "HTTP" in dummy.line.entries
    assert 400 in dummy.line.entries
    assert dummy.error_called is True
