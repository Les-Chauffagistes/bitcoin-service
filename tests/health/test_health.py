import pytest

from src.health import health


@pytest.mark.asyncio
async def test_health_returns_200():
    response = await health(None)
    assert response.status == 200
