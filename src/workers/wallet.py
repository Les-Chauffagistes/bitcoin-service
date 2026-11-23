from datetime import datetime

from src.modules.bitcoin_cli.client import Client, RpcError

# Code JSON-RPC « wallet introuvable » (RPC_WALLET_NOT_FOUND)
_WALLET_NOT_FOUND = -18


async def ensure_wallet(node: Client, name: str) -> None:
    """Charge le wallet watch-only, ou le crée (sans clé privée, descripteurs) s'il n'existe pas."""
    if name in await node.list_wallets():
        return
    try:
        await node.load_wallet(name)
    except RpcError as exc:
        if exc.code != _WALLET_NOT_FOUND:
            raise
        await node.create_wallet(name)


async def descriptor_range_end(wallet: Client, descriptor: str) -> int | None:
    """Fin de la plage importée pour ce descripteur, ou None s'il n'est pas encore dans le wallet."""
    for entry in await wallet.list_descriptors():
        if entry["desc"] == descriptor:
            return entry["range"][1]
    return None


async def import_range(wallet: Client, descriptor: str, end: int, since: datetime | None) -> None:
    """Importe (ou étend) la plage `0..end`. `since` : date de la plus ancienne facture, pour rattraper
    des paiements reçus pendant que le wallet n'existait pas ; None : « now », pas de rescan."""
    timestamp = int(since.timestamp()) - 3600 if since else "now"
    results = await wallet.import_descriptors(
        [{"desc": descriptor, "active": False, "range": [0, end], "timestamp": timestamp}]
    )
    failures = [r for r in results if not r.get("success")]
    if failures:
        raise RuntimeError(f"importdescriptors a échoué : {failures}")
