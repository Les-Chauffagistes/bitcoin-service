from decimal import Decimal

SATS_PER_BTC = 100_000_000


def eur_cents_to_sats(amount_cents: int, btc_price_eur_cents: int) -> int:
    """Sats d'un montant en centimes d'euro, arrondis au sat supérieur (même formule que le shop)."""
    if amount_cents < 0 or btc_price_eur_cents <= 0:
        raise ValueError("Invalid amount or BTC price")
    return (amount_cents * SATS_PER_BTC + btc_price_eur_cents - 1) // btc_price_eur_cents


def btc_to_sats(amount_btc: Decimal | float | int | str) -> int:
    """Convertit un montant en BTC (réponse RPC) en sats entiers, sans passer par un flottant binaire."""
    return int(Decimal(str(amount_btc)) * SATS_PER_BTC)
