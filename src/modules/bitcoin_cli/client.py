from decimal import Decimal
from functools import partial
from json import loads
from urllib.parse import quote

from aiohttp import ClientSession, BasicAuth

from .models.mining_info import MiningInfo


class RpcError(RuntimeError):
    """Erreur renvoyée par le nœud ; `code` est le code JSON-RPC (ex. -18 : wallet introuvable)."""

    def __init__(self, error: dict):
        super().__init__(f"Bitcoin RPC error: {error}")
        self.code = error.get("code")


# Les montants du nœud sont lus en Decimal : jamais de flottant binaire pour de l'argent
_loads = partial(loads, parse_float=Decimal)


class Client:
    def __init__(self, host: str, port: int, user: str, password: str, wallet: str | None = None):
        self._url = f"http://{host}:{port}/" + (f"wallet/{quote(wallet, safe='')}" if wallet else "")
        self._auth = BasicAuth(user, password)
        self._session: ClientSession | None = None

    def _get_session(self) -> ClientSession:
        if self._session is None or self._session.closed:
            self._session = ClientSession(auth=self._auth)
        return self._session

    async def _call(self, method: str, params: list = []) -> dict:
        session = self._get_session()
        payload = {"jsonrpc": "1.0", "id": "curl", "method": method, "params": params}
        async with session.post(self._url, json=payload) as resp:
            data = await resp.json(content_type=None, loads=_loads)
            if data.get("error"):
                raise RpcError(data["error"])
            return data["result"]

    async def get_mining_info(self) -> MiningInfo:
        result = await self._call("getmininginfo")
        return MiningInfo(**result)

    async def get_blockchain_info(self) -> dict:
        return await self._call("getblockchaininfo")

    async def get_descriptor_info(self, descriptor: str) -> dict:
        return await self._call("getdescriptorinfo", [descriptor])

    async def derive_addresses(self, descriptor: str, start: int, end: int) -> list[str]:
        return await self._call("deriveaddresses", [descriptor, [start, end]])

    async def estimate_smart_fee(self, conf_target: int) -> dict:
        return await self._call("estimatesmartfee", [conf_target])

    async def list_wallets(self) -> list[str]:
        return await self._call("listwallets")

    async def create_wallet(self, name: str) -> dict:
        # watch-only (pas de clé privée), vide, descripteurs
        return await self._call("createwallet", [name, True, True, "", False, True, True])

    async def load_wallet(self, name: str) -> dict:
        return await self._call("loadwallet", [name])

    async def import_descriptors(self, requests: list[dict]) -> list[dict]:
        return await self._call("importdescriptors", [requests])

    async def list_since_block(self, block_hash: str | None, target_confirmations: int) -> dict:
        # include_watchonly=true, include_removed=true (transactions sorties de la chaîne par une réorganisation)
        return await self._call("listsinceblock", [block_hash or "", target_confirmations, True, True])

    async def get_block_header(self, block_hash: str) -> dict:
        return await self._call("getblockheader", [block_hash])

    async def list_descriptors(self) -> list[dict]:
        return (await self._call("listdescriptors"))["descriptors"]
