from unittest.mock import AsyncMock, MagicMock

import pytest

from src.modules.bitcoin_cli.client import Client


@pytest.mark.asyncio
async def test_call_returns_rpc_result():
    client = Client("localhost", 8332, "user", "password")
    response = AsyncMock()
    response.json.return_value = {"result": {"blocks": 123}, "error": None}
    response.__aenter__.return_value = response
    response.__aexit__.return_value = None

    session = MagicMock()
    session.closed = False
    session.post.return_value = response
    client._session = session

    result = await client._call("getmininginfo", [])

    assert result == {"blocks": 123}
    session.post.assert_called_once_with(
        "http://localhost:8332/",
        json={"jsonrpc": "1.0", "id": "curl", "method": "getmininginfo", "params": []},
    )


@pytest.mark.asyncio
async def test_call_raises_on_rpc_error():
    client = Client("localhost", 8332, "user", "password")
    response = AsyncMock()
    response.json.return_value = {"result": None, "error": {"code": -1, "message": "boom"}}
    response.__aenter__.return_value = response
    response.__aexit__.return_value = None

    session = MagicMock()
    session.closed = False
    session.post.return_value = response
    client._session = session

    with pytest.raises(RuntimeError, match="Bitcoin RPC error"):
        await client._call("getmininginfo", [])


@pytest.mark.asyncio
async def test_get_mining_info_builds_model():
    client = Client("localhost", 8332, "user", "password")
    client._call = AsyncMock(
        return_value={
            "blocks": 840000,
            "difficulty": 123.45,
            "networkhashps": 10.0,
            "pooledtx": 42,
            "chain": "main",
            "warnings": [],
        }
    )

    info = await client.get_mining_info()

    assert info.blocks == 840000
    assert info.difficulty == 123.45
