import time
from contextlib import contextmanager
from decimal import Decimal
from typing import Iterator

from prisma import Prisma
from prisma.errors import PrismaError, UniqueViolationError
from prisma.models import Invoice

from src.modules.bitcoin_cli.instance import rpc
from src.modules.db import db
from src.settings import settings
from src.utils.alerts import alert
from src.utils.money import eur_cents_to_sats

from ..errors import ApiError
from . import market
from .derivation import AddressDeriver

_deriver: AddressDeriver | None = None


def get_deriver() -> AddressDeriver:
    global _deriver
    if _deriver is None:
        _deriver = AddressDeriver(rpc, settings.xpub, settings.bitcoin_network)
    return _deriver


@contextmanager
def db_guard() -> Iterator[None]:
    """Une panne de base (failover du cluster, connexion coupée) répond 503, jamais une adresse non enregistrée."""
    try:
        yield
    except UniqueViolationError:
        raise
    except PrismaError as exc:
        alert("db_unavailable", "Base de données indisponible", level="WARNING", error=str(exc))
        raise ApiError(503, "db_unavailable", "Base de données indisponible.") from exc


async def get_btc_price_eur_cents() -> int:
    """Prix d'un bitcoin en centimes d'euro, ou 503 si la source est indisponible ou périmée (jamais de taux périmé)."""
    try:
        data = await market.get_price()
        eur = Decimal(str(data["EUR"]))
        age = time.time() - float(data["time"])
        if eur <= 0 or age > settings.price_max_age_seconds:
            raise ValueError(f"taux invalide ou périmé (EUR={eur}, âge={age:.0f}s)")
        return int(eur * 100)
    except Exception as exc:
        alert("price_unavailable", "Taux BTC/EUR indisponible", level="WARNING", error=str(exc))
        raise ApiError(503, "price_unavailable", "Taux BTC/EUR indisponible.") from exc


def _existing_or_conflict(invoice: Invoice, amount_cents: int) -> Invoice:
    if invoice.amountCents != amount_cents:
        raise ApiError(409, "invoice_conflict", "Cette facture existe déjà avec un autre montant.")
    return invoice


async def create_invoice(order_id: str, amount_cents: int, client: Prisma = db) -> tuple[Invoice, bool]:
    """Crée la facture ou renvoie l'existante (idempotent sur `order_id`). Vrai si elle vient d'être créée.

    L'adresse n'est renvoyée qu'une fois la ligne enregistrée. Deux appels simultanés pour le même
    `order_id` consomment chacun un index : le second perd la course sur l'unicité de `order_id` et
    relit la facture du premier (l'index perdu est sans conséquence).
    """
    with db_guard():
        existing = await client.invoice.find_unique(where={"orderId": order_id})
        if existing:
            return _existing_or_conflict(existing, amount_cents), False

        price = await get_btc_price_eur_cents()
        rows = await client.query_raw("SELECT nextval(pg_get_serial_sequence('invoice', 'derivation_index'))::int AS idx")
        index = int(rows[0]["idx"])
        try:
            address = await get_deriver().address(index)
        except Exception as exc:
            alert("node_unreachable", "Dérivation d'adresse impossible", level="WARNING", error=str(exc))
            raise ApiError(503, "wallet_unavailable", "Dérivation d'adresse indisponible.") from exc

        try:
            invoice = await client.invoice.create(
                data={
                    "orderId": order_id,
                    "derivationIndex": index,
                    "address": address,
                    "amountCents": amount_cents,
                    "btcPriceEurCents": price,
                    "expectedSats": eur_cents_to_sats(amount_cents, price),
                }
            )
        except UniqueViolationError:
            winner = await client.invoice.find_unique(where={"orderId": order_id})
            if winner is None:
                raise
            return _existing_or_conflict(winner, amount_cents), False
        return invoice, True


async def get_invoice(order_id: str, client: Prisma = db) -> Invoice:
    with db_guard():
        invoice = await client.invoice.find_unique(where={"orderId": order_id}, include={"outputs": True})
    if invoice is None:
        raise ApiError(404, "invoice_not_found", "Facture introuvable.")
    return invoice
