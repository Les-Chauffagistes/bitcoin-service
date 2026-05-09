from datetime import datetime, timedelta
from typing import Any

from aiohttp import ClientSession

_cache: dict[str, tuple[datetime, Any]] = {}
_session: ClientSession | None = None


def _get_session() -> ClientSession:
    global _session
    if _session is None or _session.closed:
        _session = ClientSession()
    return _session


async def cached_get(url: str, ttl: int = 30) -> Any:
    now = datetime.now()
    entry = _cache.get(url)
    if entry is not None:
        cached_at, body = entry
        if now - cached_at < timedelta(seconds=ttl):
            return body

    session = _get_session()
    async with session.get(url) as response:
        body = await response.json()

    _cache[url] = (now, body)
    return body
