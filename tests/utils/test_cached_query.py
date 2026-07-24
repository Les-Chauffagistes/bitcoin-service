from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.utils import cached_query


@pytest.fixture(autouse=True)
def reset_cache_state():
    cached_query._cache.clear()
    cached_query._session = None
    yield
    cached_query._cache.clear()
    cached_query._session = None


@pytest.mark.asyncio
async def test_cached_get_uses_cache_before_network():
    cached_query._cache["https://a"] = (datetime.now(), {"ok": True})

    result = await cached_query.cached_get("https://a", ttl=30)

    assert result == {"ok": True}


@pytest.mark.asyncio
async def test_cached_get_fetches_and_stores_response():
    response = MagicMock()
    response.raise_for_status.return_value = None
    response.json = AsyncMock(return_value={"price": 1})
    response.__aenter__ = AsyncMock(return_value=response)
    response.__aexit__ = AsyncMock(return_value=None)

    session = MagicMock()
    session.closed = False
    session.get.return_value = response

    with patch("src.utils.cached_query.ClientSession", return_value=session):
        result = await cached_query.cached_get("https://a", ttl=30)

    assert result == {"price": 1}
    assert "https://a" in cached_query._cache


@pytest.mark.asyncio
async def test_cached_get_tries_next_url_when_first_fails():
    bad_response = MagicMock()
    bad_response.raise_for_status.side_effect = RuntimeError("boom")
    bad_response.__aenter__ = AsyncMock(return_value=bad_response)
    bad_response.__aexit__ = AsyncMock(return_value=None)

    good_response = MagicMock()
    good_response.raise_for_status.return_value = None
    good_response.json = AsyncMock(return_value={"value": 42})
    good_response.__aenter__ = AsyncMock(return_value=good_response)
    good_response.__aexit__ = AsyncMock(return_value=None)

    session = MagicMock()
    session.closed = False
    session.get.side_effect = [bad_response, good_response]

    with patch("src.utils.cached_query.ClientSession", return_value=session):
        result = await cached_query.cached_get(["https://bad", "https://good"], ttl=30)

    assert result == {"value": 42}


@pytest.mark.asyncio
async def test_cached_get_raises_last_error_when_all_urls_fail():
    expired = datetime.now() - timedelta(seconds=120)
    cached_query._cache["https://bad"] = (expired, {"stale": True})

    response = MagicMock()
    response.raise_for_status.side_effect = RuntimeError("still down")
    response.__aenter__ = AsyncMock(return_value=response)
    response.__aexit__ = AsyncMock(return_value=None)

    session = MagicMock()
    session.closed = False
    session.get.return_value = response

    with patch("src.utils.cached_query.ClientSession", return_value=session):
        with pytest.raises(RuntimeError, match="still down"):
            await cached_query.cached_get(["https://bad"], ttl=1)
