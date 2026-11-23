from decimal import Decimal

import pytest

from src.utils.money import btc_to_sats, eur_cents_to_sats


@pytest.mark.parametrize(
    ("cents", "price", "expected"),
    [
        (119_000, 9_000_000, 1_322_223),  # 1 190 € à 90 000 €/BTC, arrondi au sat supérieur
        (9_000_000, 9_000_000, 100_000_000),
        (1, 9_000_000, 12),  # 11,11 sats arrondis au supérieur
        (0, 9_000_000, 0),
    ],
)
def test_eur_cents_to_sats_rounds_up(cents, price, expected):
    assert eur_cents_to_sats(cents, price) == expected


@pytest.mark.parametrize(("cents", "price"), [(-1, 1), (1, 0), (1, -5)])
def test_eur_cents_to_sats_rejects_invalid(cents, price):
    with pytest.raises(ValueError):
        eur_cents_to_sats(cents, price)


@pytest.mark.parametrize(
    ("btc", "sats"),
    [(0.00000001, 1), (Decimal("0.00150000"), 150_000), (1.1, 110_000_000), ("21000000", 2_100_000_000_000_000)],
)
def test_btc_to_sats_is_exact(btc, sats):
    assert btc_to_sats(btc) == sats
