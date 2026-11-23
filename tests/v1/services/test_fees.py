from unittest.mock import AsyncMock

import pytest

from src.v1.errors import ApiError
from src.v1.services import fees


@pytest.fixture(autouse=True)
def reset_cache(monkeypatch):
    monkeypatch.setattr(fees, "_cache", None)


@pytest.mark.parametrize(
    ("feerate", "expected"),
    [
        ("0.00010000", 1_410),  # 10 sat/vB × 141 vB
        ("0.00001000", 500),  # sous le plancher
        ("0.01000000", 20_000),  # au-dessus du plafond
    ],
)
def test_fee_sats_from_feerate_is_clamped(feerate, expected):
    assert fees.fee_sats_from_feerate(feerate) == expected


@pytest.mark.asyncio
async def test_estimate_is_cached(monkeypatch):
    rpc = AsyncMock()
    rpc.estimate_smart_fee.return_value = {"feerate": 0.0001, "blocks": 6}
    monkeypatch.setattr(fees, "rpc", rpc)

    assert await fees.get_refund_fee_sats() == 1_410
    assert await fees.get_refund_fee_sats() == 1_410
    rpc.estimate_smart_fee.assert_awaited_once_with(6)


@pytest.mark.asyncio
async def test_unavailable_without_previous_value(monkeypatch):
    rpc = AsyncMock()
    rpc.estimate_smart_fee.return_value = {"errors": ["Insufficient data or no feerate found"]}
    monkeypatch.setattr(fees, "rpc", rpc)

    with pytest.raises(ApiError) as exc:
        await fees.get_refund_fee_sats()
    assert (exc.value.status, exc.value.code) == (503, "fee_unavailable")


@pytest.mark.asyncio
async def test_last_known_value_when_node_is_silent(monkeypatch):
    rpc = AsyncMock()
    rpc.estimate_smart_fee.side_effect = RuntimeError("down")
    monkeypatch.setattr(fees, "rpc", rpc)
    monkeypatch.setattr(fees.time, "monotonic", lambda: 1_000.0)
    monkeypatch.setattr(fees, "_cache", (1_000.0 - 600, 777))  # périmée pour le cache, valable pour le repli

    assert await fees.get_refund_fee_sats() == 777
