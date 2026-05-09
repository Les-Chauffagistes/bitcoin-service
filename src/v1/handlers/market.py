from aiohttp.web import Request, json_response

from ..app import routes
from ..services import market
from init import log

log.info("routes defined")


@routes.get("/bitcoin-price")
async def get_price(_: Request):
    price = await market.get_price()
    return json_response(price)