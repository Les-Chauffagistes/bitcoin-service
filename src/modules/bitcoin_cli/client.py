from aiohttp import ClientSession, BasicAuth

from .models.mining_info import MiningInfo


class Client:
    def __init__(self, host: str, port: int, user: str, password: str):
        self._url = f"http://{host}:{port}/"
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
            print(resp)
            data = await resp.json(content_type=None)
            if data.get("error"):
                raise RuntimeError(f"Bitcoin RPC error: {data['error']}")
            return data["result"]

    async def get_mining_info(self) -> MiningInfo:
        result = await self._call("getmininginfo")
        return MiningInfo(**result)