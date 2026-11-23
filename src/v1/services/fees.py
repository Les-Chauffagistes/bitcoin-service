import time
from decimal import Decimal

from src.modules.bitcoin_cli.instance import rpc
from src.settings import settings
from src.utils.alerts import alert
from src.utils.money import SATS_PER_BTC

from ..errors import ApiError

CONF_TARGET = 6
# Transaction P2WPKH, 1 entrée et 2 sorties
TX_VSIZE = 141
CACHE_TTL_SECONDS = 60
STALE_TTL_SECONDS = 3600

_cache: tuple[float, int] | None = None


def fee_sats_from_feerate(feerate_btc_per_kvb: Decimal | float | str) -> int:
    """Frais d'une transaction type en sats, bornés par FEE_MIN_SATS et FEE_MAX_SATS."""
    sats_per_vb = Decimal(str(feerate_btc_per_kvb)) * SATS_PER_BTC / 1000
    fee = int((sats_per_vb * TX_VSIZE).to_integral_value(rounding="ROUND_CEILING"))
    return max(settings.fee_min_sats, min(settings.fee_max_sats, fee))


async def get_refund_fee_sats() -> int:
    global _cache
    now = time.monotonic()
    if _cache is not None and now - _cache[0] < CACHE_TTL_SECONDS:
        return _cache[1]
    try:
        estimate = await rpc.estimate_smart_fee(CONF_TARGET)
        if "feerate" not in estimate:
            raise RuntimeError(f"Pas d'estimation de frais : {estimate.get('errors')}")
        fee = fee_sats_from_feerate(estimate["feerate"])
    except Exception as exc:
        # Nœud muet : dernière valeur connue si elle a moins d'une heure, sinon 503
        if _cache is not None and now - _cache[0] < STALE_TTL_SECONDS:
            return _cache[1]
        alert("node_unreachable", "Estimation des frais impossible", level="WARNING", error=str(exc))
        raise ApiError(503, "fee_unavailable", "Estimation des frais indisponible.") from exc
    _cache = (now, fee)
    return fee
