from src.utils.cached_query import cached_get

PRICE_URLS = [
    "https://mempool.space/api/v1/prices",
]


async def get_price():
    return await cached_get(PRICE_URLS)