import re

from aiohttp.web import Request, json_response

from src.middlewares.authorization import require_auth

from ..app import routes
from ..errors import ApiError, json_errors
from ..services import deliveries, invoices

_ORDER_ID = re.compile(r"^[A-Za-z0-9_-]{1,100}$")
_AMOUNT_CENTS = re.compile(r"^[1-9]\d{0,17}$")


def _invoice_json(invoice) -> dict:
    return {
        "address": invoice.address,
        "expectedSats": str(invoice.expectedSats),
        "btcPriceEurCents": str(invoice.btcPriceEurCents),
    }


@routes.post("/invoices")
@require_auth
@json_errors
async def create_invoice(request: Request):
    try:
        body = await request.json()
    except ValueError:
        body = None
    if (
        not isinstance(body, dict)
        or set(body) != {"orderId", "amountCents"}
        or not isinstance(body["orderId"], str)
        or not _ORDER_ID.match(body["orderId"])
        or not isinstance(body["amountCents"], str)
        or not _AMOUNT_CENTS.match(body["amountCents"])
    ):
        raise ApiError(400, "invalid_payload", 'Attendu : { "orderId": string, "amountCents": "<entier > 0>" }.')

    invoice, created = await invoices.create_invoice(body["orderId"], int(body["amountCents"]))
    return json_response(_invoice_json(invoice), status=201 if created else 200)


@routes.get("/invoices/{order_id}")
@require_auth
@json_errors
async def get_invoice(request: Request):
    invoice = await invoices.get_invoice(request.match_info["order_id"])
    return json_response(
        {
            "orderId": invoice.orderId,
            **_invoice_json(invoice),
            "amountCents": str(invoice.amountCents),
            "createdAt": invoice.createdAt.isoformat(),
            "outputs": [
                {
                    "txid": output.txid,
                    "vout": output.vout,
                    "amountSats": str(output.amountSats),
                    "confirmations": output.confirmations,
                    "blockHeight": output.blockHeight,
                    "notifiedAt": output.notifiedAt.isoformat() if output.notifiedAt else None,
                }
                for output in invoice.outputs or []
            ],
        }
    )


@routes.post("/invoices/{order_id}/replay")
@require_auth
@json_errors
async def replay_invoice(request: Request):
    return json_response({"queued": await deliveries.replay_invoice(request.match_info["order_id"])})
