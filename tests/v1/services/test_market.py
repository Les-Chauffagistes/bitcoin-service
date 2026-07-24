from unittest.mock import AsyncMock, patch

import pytest

from src.v1.services import market


@pytest.mark.asyncio
async def test_get_price_delegates_to_cached_get():
    with patch("src.v1.services.market.cached_get", AsyncMock(return_value={"USD": 99999})) as mocked:
        result = await market.get_price()

    assert result == {"USD": 99999}
    mocked.assert_awaited_once_with(market.PRICE_URLS)
