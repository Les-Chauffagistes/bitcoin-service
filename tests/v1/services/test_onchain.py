from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.v1.services import onchain


@pytest.mark.asyncio
async def test_get_block_height_uses_rpc_result(monkeypatch):
    monkeypatch.setattr(
        onchain.client,
        "get_mining_info",
        AsyncMock(return_value=MagicMock(blocks=910000, difficulty=1.0)),
    )

    result = await onchain.get_block_height()

    assert result == 910000


@pytest.mark.asyncio
async def test_get_difficulty_uses_rpc_result(monkeypatch):
    monkeypatch.setattr(
        onchain.client,
        "get_mining_info",
        AsyncMock(return_value=MagicMock(blocks=910000, difficulty=456.7)),
    )

    result = await onchain.get_difficulty()

    assert result == 456.7


@pytest.mark.asyncio
async def test_get_block_reward_uses_halving_formula(monkeypatch):
    # 210_000 * 4 => era 4 => 50 / 16 = 3.125
    monkeypatch.setattr(
        onchain.client,
        "get_mining_info",
        AsyncMock(return_value=MagicMock(blocks=840000, difficulty=1.0)),
    )

    result = await onchain.get_block_reward()

    assert result == 3.125


@pytest.mark.asyncio
async def test_get_difficulty_falls_back_to_http_when_rpc_fails(monkeypatch):
    monkeypatch.setattr(
        onchain.client,
        "get_mining_info",
        AsyncMock(side_effect=RuntimeError("rpc down")),
    )

    response = MagicMock()
    response.raise_for_status.return_value = None
    response.text = AsyncMock(return_value="123.456")
    response.__aenter__ = AsyncMock(return_value=response)
    response.__aexit__ = AsyncMock(return_value=None)

    session = MagicMock()
    session.get.return_value = response
    session_cm = MagicMock()
    session_cm.__aenter__ = AsyncMock(return_value=session)
    session_cm.__aexit__ = AsyncMock(return_value=None)

    with patch("src.v1.services.onchain.ClientSession", return_value=session_cm):
        result = await onchain.get_difficulty()

    assert result == 123.456


@pytest.mark.asyncio
async def test_get_block_reward_falls_back_to_http_when_rpc_fails(monkeypatch):
    monkeypatch.setattr(
        onchain.client,
        "get_mining_info",
        AsyncMock(side_effect=RuntimeError("rpc down")),
    )

    response = MagicMock()
    response.raise_for_status.return_value = None
    response.text = AsyncMock(return_value="6.25")
    response.__aenter__ = AsyncMock(return_value=response)
    response.__aexit__ = AsyncMock(return_value=None)

    session = MagicMock()
    session.get.return_value = response
    session_cm = MagicMock()
    session_cm.__aenter__ = AsyncMock(return_value=session)
    session_cm.__aexit__ = AsyncMock(return_value=None)

    with patch("src.v1.services.onchain.ClientSession", return_value=session_cm):
        result = await onchain.get_block_reward()

    assert result == 6.25
