from unittest.mock import AsyncMock

import pytest

from src.v1.services.derivation import AddressDeriver, NetworkMismatch

XPUB = "xpub6CatWdiZiodmUeTDp8LT5or8nmbKNcuyvz7WyksVFkKB4RHwCD3XyuvPEbvqAQY3rAPshWcMLoP2fMFMKHPJ4ZeZXYVUhLv1VMrjPC7PW6V"


def _client(chain="main"):
    client = AsyncMock()
    client.get_blockchain_info.return_value = {"chain": chain}
    client.get_descriptor_info.return_value = {"descriptor": f"wpkh({XPUB}/0/*)#abcd1234", "checksum": "abcd1234"}
    client.derive_addresses.return_value = ["bc1qaddress"]
    return client


@pytest.mark.asyncio
async def test_address_uses_checksummed_descriptor():
    client = _client()
    deriver = AddressDeriver(client, XPUB, "main")

    assert await deriver.address(7) == "bc1qaddress"

    client.get_descriptor_info.assert_awaited_once_with(f"wpkh({XPUB}/0/*)")
    client.derive_addresses.assert_awaited_once_with(f"wpkh({XPUB}/0/*)#abcd1234", 7, 7)


@pytest.mark.asyncio
async def test_descriptor_and_network_are_checked_once():
    client = _client()
    deriver = AddressDeriver(client, XPUB, "main")

    await deriver.address(1)
    await deriver.address(2)

    client.get_blockchain_info.assert_awaited_once()
    client.get_descriptor_info.assert_awaited_once()


@pytest.mark.asyncio
async def test_node_on_another_network_is_refused():
    deriver = AddressDeriver(_client(chain="testnet4"), XPUB, "main")
    with pytest.raises(NetworkMismatch):
        await deriver.address(1)


def test_invalid_key_refuses_to_start():
    with pytest.raises(ValueError):
        AddressDeriver(_client(), XPUB, "regtest")
