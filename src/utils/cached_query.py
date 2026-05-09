from datetime import datetime, timedelta
from typing import Any

from aiohttp import ClientSession

CACHE_DURATION_SECONDS = 30


class CachedResult:
    def __init__(self, date: datetime, url: str, body: Any):
        self.date = date
        self.url = url
        self.body = body
    
    def is_valid(self, date: datetime | None = None, cache_duration: int = CACHE_DURATION_SECONDS):
        if not date:
            date = datetime.now()
        
        return date - self.date < timedelta(seconds=cache_duration)
             
    def __eq__(self, value: object) -> bool:
        if isinstance(value, CachedResult):
            return self.url == value.url
        return False

cache: dict[str, CachedResult] = {}

async def make_cached_query(url: str):
    cached = cache.get(url)
    if cached and cached.is_valid():
        return cached.body
    else:
        async with ClientSession() as session:
            pass