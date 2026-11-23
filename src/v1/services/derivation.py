from src.modules.bitcoin_cli.client import Client
from src.modules.xpub import normalize_xpub
from src.settings import settings


class NetworkMismatch(Exception):
    """Le nœud n'est pas sur le réseau configuré."""


class AddressDeriver:
    """Dérive les adresses de réception P2WPKH `wpkh(xpub/0/*)` avec `deriveaddresses` du nœud."""

    def __init__(self, client: Client, xpub: str, network: str):
        self._client = client
        self._network = network
        # Refuse de démarrer (ValueError) si la clé est invalide ou d'un autre réseau
        self._xpub = normalize_xpub(xpub, network)
        self._descriptor: str | None = None
        self._network_checked = False

    async def check_network(self) -> None:
        if self._network_checked:
            return
        chain = (await self._client.get_blockchain_info())["chain"]
        if chain != self._network:
            raise NetworkMismatch(f"Le nœud est sur le réseau {chain}, {self._network} attendu")
        self._network_checked = True

    async def _get_descriptor(self) -> str:
        if self._descriptor is None:
            info = await self._client.get_descriptor_info(f"wpkh({self._xpub}/0/*)")
            # `descriptor` contient déjà le `#checksum` exigé par deriveaddresses
            self._descriptor = info["descriptor"]
        return self._descriptor

    async def address(self, index: int) -> str:
        await self.check_network()
        addresses = await self._client.derive_addresses(await self._get_descriptor(), index, index)
        return addresses[0]
