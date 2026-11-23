from datetime import datetime, timezone

from prisma import Prisma

from src.modules.db import db
from src.settings import settings

from ..errors import ApiError
from .invoices import db_guard


async def replay_invoice(order_id: str, client: Prisma = db) -> int:
    """Remet en file l'envoi de toutes les sorties de la facture (réconciliation manuelle).

    Le shop est idempotent sur (txid, vout) : renvoyer une sortie déjà livrée est sans risque. La fenêtre
    de 72 h repart de zéro. Les sorties sous le seuil de confirmations ou de poussière ne sont pas concernées.
    """
    with db_guard():
        invoice = await client.invoice.find_unique(where={"orderId": order_id}, include={"outputs": True})
        if invoice is None:
            raise ApiError(404, "invoice_not_found", "Facture introuvable.")
        now = datetime.now(timezone.utc)
        queued = 0
        for output in invoice.outputs or []:
            if output.confirmations < settings.min_confirmations or output.amountSats <= settings.dust_sats:
                continue
            await client.webhookdelivery.upsert(
                where={"txid_vout": {"txid": output.txid, "vout": output.vout}},
                data={
                    "create": {"txid": output.txid, "vout": output.vout},
                    "update": {
                        "attempts": 0,
                        "nextAttemptAt": now,
                        "createdAt": now,
                        "deliveredAt": None,
                        "failedAt": None,
                        "failReason": None,
                        "lastStatusCode": None,
                        "lastError": None,
                    },
                },
            )
            queued += 1
        return queued
