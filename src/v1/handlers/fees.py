from aiohttp.web import Request, json_response

from src.middlewares.authorization import require_auth

from ..app import routes
from ..errors import json_errors
from ..services import fees


@routes.get("/fee-estimate")
@require_auth
@json_errors
async def get_fee_estimate(_: Request):
    return json_response({"refundNetworkFeeSats": str(await fees.get_refund_fee_sats())})
