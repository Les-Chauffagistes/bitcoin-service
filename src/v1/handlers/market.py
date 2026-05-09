from aiohttp.web import Request, json_response

from ..app import routes
from ..services import market


@routes.get("/price")
async def get_price(_: Request):
    price = await market.get_price()
    return json_response(price)