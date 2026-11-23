"""Envoi du webhook au shop : lit la file `webhook_delivery`, réessaie avec backoff.

Il ne regarde jamais la chaîne : le scanner (`scanner.py`) met les livraisons en file, l'envoi les
consomme. Plusieurs instances peuvent tourner ensemble : une livraison est réservée (`FOR UPDATE SKIP
LOCKED`, puis un bail court) avant d'être envoyée.
"""
import asyncio
from datetime import datetime, timedelta, timezone
from enum import Enum

from aiohttp import ClientError, ClientSession, ClientTimeout
from prisma import Prisma
from prisma.errors import PrismaError

from chauff_cmn.logging import logger as log
from src.utils.alerts import alert

from .backoff import retry_delay

# Après 72 h sans succès, la livraison est abandonnée (rejouable à la main : POST …/replay)
RETRY_WINDOW = timedelta(hours=72)
# Un 404 (facture pas encore visible côté shop) est attendu un court instant, pas plus d'une heure
UNKNOWN_ADDRESS_GRACE = timedelta(hours=1)
# Statuts du shop qui valent « réessayer » même s'ils sont en 4xx
RETRYABLE_4XX = {404, 408, 425, 429}
HELD_RECHECK = timedelta(seconds=60)
# Avis « paiement vu » : utile seulement pendant la réservation du shop (30 min), abandonné ensuite sans bruit
SEEN_WINDOW = timedelta(minutes=30)
BATCH = 10

_CLAIM_SQL = """
UPDATE webhook_delivery
SET next_attempt_at = now() + make_interval(secs => $1::double precision)
WHERE id IN (
  SELECT id FROM webhook_delivery
  WHERE delivered_at IS NULL AND failed_at IS NULL AND next_attempt_at <= now()
  ORDER BY next_attempt_at
  LIMIT $2::int
  FOR UPDATE SKIP LOCKED
)
RETURNING id::text AS id, txid, vout, attempts, created_at
"""

_CLAIM_SEEN_SQL = """
UPDATE seen_notice
SET next_attempt_at = now() + make_interval(secs => $1::double precision)
WHERE id IN (
  SELECT id FROM seen_notice
  WHERE delivered_at IS NULL AND failed_at IS NULL AND next_attempt_at <= now()
  ORDER BY next_attempt_at
  LIMIT $2::int
  FOR UPDATE SKIP LOCKED
)
RETURNING id::text AS id, invoice_id::text AS invoice_id, txid, vout, total_sats::text AS total_sats, attempts, created_at
"""


class Outcome(Enum):
    DELIVERED = "delivered"
    RETRY = "retry"
    REJECTED = "rejected"


def classify(status: int) -> Outcome:
    """Réponse du shop → conduite (contrat §5.2)."""
    if status in (200, 201):
        return Outcome.DELIVERED
    if status >= 500 or status in RETRYABLE_4XX:
        return Outcome.RETRY
    return Outcome.REJECTED  # 400, 401, 409… : contrat ou secret erroné, anomalie à traiter à la main


class Sender:
    def __init__(
        self,
        *,
        db: Prisma,
        url: str,
        secret: str,
        min_confirmations: int,
        interval_seconds: float,
        timeout_seconds: float = 10,
        session: ClientSession | None = None,
    ):
        self._db = db
        self._url = url
        self._seen_url = url.rstrip("/") + "/seen"
        self._headers = {"Authorization": f"Bearer {secret}"}
        self._min_confirmations = min_confirmations
        self._interval = interval_seconds
        self._timeout = ClientTimeout(total=timeout_seconds)
        # Bail de réservation : une instance qui meurt en plein envoi laisse la livraison reprise ensuite
        self._claim_seconds = timeout_seconds + 60
        self._session = session

    def _get_session(self) -> ClientSession:
        if self._session is None or self._session.closed:
            self._session = ClientSession(timeout=self._timeout)
        return self._session

    async def tick(self) -> int:
        """Envoie les livraisons dues ; renvoie le nombre traité."""
        claimed = await self._db.query_raw(_CLAIM_SQL, self._claim_seconds, BATCH)
        results = await asyncio.gather(*(self._deliver(row) for row in claimed), return_exceptions=True)
        for result in results:
            if isinstance(result, Exception):
                log.opt(exception=result).error("Erreur inattendue pendant un envoi")
        return len(claimed) + await self._tick_seen()

    async def _tick_seen(self) -> int:
        claimed = await self._db.query_raw(_CLAIM_SEEN_SQL, self._claim_seconds, BATCH)
        results = await asyncio.gather(*(self._deliver_seen(row) for row in claimed), return_exceptions=True)
        for result in results:
            if isinstance(result, Exception):
                log.opt(exception=result).error("Erreur inattendue pendant l'envoi d'un avis « paiement vu »")
        return len(claimed)

    async def _deliver_seen(self, row: dict) -> None:
        """Avis au mieux : le shop arrête le décompte de sa réservation. Réessais courts, jamais d'alerte (le
        webhook de confirmation reste la référence)."""
        invoice = await self._db.invoice.find_unique(where={"id": row["invoice_id"]})
        now = datetime.now(timezone.utc)
        created_at = row["created_at"]
        if isinstance(created_at, str):
            created_at = datetime.fromisoformat(created_at)
        attempts = row["attempts"] + 1
        status: int | None = None
        try:
            payload = {"address": invoice.address, "txid": row["txid"], "vout": row["vout"], "totalSats": row["total_sats"]}
            async with self._get_session().post(self._seen_url, json=payload, headers=self._headers) as response:
                status = response.status
        except (ClientError, asyncio.TimeoutError, OSError) as exc:
            log.warning("Avis « paiement vu » : échec d'envoi ({})", type(exc).__name__)

        outcome = Outcome.RETRY if status is None else classify(status)
        if outcome is Outcome.DELIVERED:
            await self._db.seennotice.update(
                where={"id": row["id"]}, data={"deliveredAt": now, "attempts": attempts, "lastStatusCode": status}
            )
            log.info("Avis « paiement vu » livré (facture {}, essai {})", invoice.orderId, attempts)
        elif outcome is Outcome.REJECTED or now - created_at >= SEEN_WINDOW:
            log.warning("Avis « paiement vu » abandonné (facture {}, statut {})", invoice.orderId, status)
            await self._db.seennotice.update(
                where={"id": row["id"]}, data={"failedAt": now, "attempts": attempts, "lastStatusCode": status}
            )
        else:
            delay = timedelta(seconds=retry_delay(attempts))
            await self._db.seennotice.update(
                where={"id": row["id"]},
                data={"nextAttemptAt": now + delay, "attempts": attempts, "lastStatusCode": status},
            )

    async def _deliver(self, row: dict) -> None:
        key = {"txid_vout": {"txid": row["txid"], "vout": row["vout"]}}
        output = await self._db.receivedoutput.find_unique(where=key, include={"invoice": True})
        now = datetime.now(timezone.utc)
        created_at = row["created_at"]
        if isinstance(created_at, str):  # une requête brute renvoie les dates en texte ISO 8601
            created_at = datetime.fromisoformat(created_at)
        age = now - created_at
        # Sortie retirée de la chaîne depuis la mise en file (réorganisation) : on n'annonce rien tant
        # qu'elle n'est pas reconfirmée ; le scanner remet la confirmation à jour
        if output is None or output.confirmations < self._min_confirmations:
            if age >= RETRY_WINDOW:
                alert("webhook_failed_permanently", "Webhook abandonné : sortie jamais reconfirmée", txid=row["txid"], vout=row["vout"])
                await self._give_up(row, "expired", None, "sortie jamais reconfirmée", now)
            else:
                await self._reschedule(row["id"], now + HELD_RECHECK, attempts=row["attempts"])
            return

        payload = {
            "address": output.address,
            "txid": output.txid,
            "vout": output.vout,
            "amountSats": str(output.amountSats),
        }
        status: int | None = None
        error: str | None = None
        body = ""
        try:
            async with self._get_session().post(self._url, json=payload, headers=self._headers) as response:
                status = response.status
                body = (await response.text())[:200]
        except (ClientError, asyncio.TimeoutError, OSError) as exc:
            error = f"{type(exc).__name__}: {exc}"

        attempts = row["attempts"] + 1
        outcome = Outcome.RETRY if status is None else classify(status)
        context = {"txid": row["txid"], "vout": row["vout"], "order_id": output.invoice.orderId, "attempts": attempts}

        if outcome is Outcome.DELIVERED:
            await self._mark_delivered(row, attempts, status, now)
        elif outcome is Outcome.REJECTED:
            alert("webhook_rejected", "Le shop a refusé le webhook (pas de réessai)", status_code=status, body=body, **context)
            await self._give_up(row, "rejected", status, body, now, attempts)
        elif age >= RETRY_WINDOW:
            alert("webhook_failed_permanently", "Webhook abandonné après 72 h de réessais", status_code=status, error=error, **context)
            await self._give_up(row, "expired", status, error or body, now, attempts)
        else:
            if status == 404:
                # Normal un court instant (la facture est créée côté shop après la réponse du service)
                level = "ERROR" if age >= UNKNOWN_ADDRESS_GRACE else "WARNING"
                alert("webhook_unknown_address", "Le shop ne connaît pas encore cette adresse", level=level, **context)
            delay = timedelta(seconds=retry_delay(attempts))
            await self._reschedule(row["id"], now + delay, attempts, status, error or body)

    async def _mark_delivered(self, row: dict, attempts: int, status: int | None, now: datetime) -> None:
        async with self._db.tx() as tx:
            await tx.webhookdelivery.update(
                where={"id": row["id"]},
                data={"deliveredAt": now, "attempts": attempts, "lastStatusCode": status, "lastError": None},
            )
            # Première notification acceptée seulement : un replay ne la réécrit pas
            await tx.execute_raw(
                "UPDATE received_output SET notified_at = $3::timestamptz WHERE txid = $1::text AND vout = $2::int AND notified_at IS NULL",
                row["txid"],
                row["vout"],
                now,
            )
        log.info("Webhook livré (txid {}, essai {})", row["txid"], attempts)

    async def _reschedule(
        self, delivery_id: str, when: datetime, attempts: int, status: int | None = None, error: str | None = None
    ) -> None:
        await self._db.webhookdelivery.update(
            where={"id": delivery_id},
            data={"nextAttemptAt": when, "attempts": attempts, "lastStatusCode": status, "lastError": error},
        )

    async def _give_up(
        self, row: dict, reason: str, status: int | None, error: str | None, now: datetime, attempts: int | None = None
    ) -> None:
        await self._db.webhookdelivery.update(
            where={"id": row["id"]},
            data={
                "failedAt": now,
                "failReason": reason,
                "lastStatusCode": status,
                "lastError": error,
                **({"attempts": attempts} if attempts is not None else {}),
            },
        )

    async def run(self) -> None:
        while True:
            try:
                await self.tick()
            except asyncio.CancelledError:
                raise
            except PrismaError as exc:
                alert("db_unavailable", "Base de données indisponible (envoi)", level="WARNING", error=str(exc))
            except Exception:
                log.exception("Erreur inattendue de l'envoi")
            await asyncio.sleep(self._interval)
