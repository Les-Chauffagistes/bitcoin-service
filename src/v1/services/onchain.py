from aiohttp import ClientSession

from src.settings import settings
from src.modules.bitcoin_cli.client import Client

client = Client(
    settings.bitcoin_rpc_host,
    settings.bitcoin_rpc_port,
    settings.bitcoin_rpc_user,
    settings.bitcoin_rpc_password,
)

_BLOCK_REWARD_FALLBACK = "https://blockchain.info/q/bcperblock"
_DIFFICULTY_FALLBACK = "https://blockchain.info/q/getdifficulty"


async def get_block_reward() -> float:
    try:
        info = await client.get_mining_info()
        era = info.blocks // 210000
        return 50 / (2**era)
    except Exception:
        async with ClientSession() as session:
            async with session.get(_BLOCK_REWARD_FALLBACK) as resp:
                resp.raise_for_status()
                return float(await resp.text())


async def get_difficulty() -> float:
    try:
        info = await client.get_mining_info()
        return info.difficulty
    except Exception:
        async with ClientSession() as session:
            async with session.get(_DIFFICULTY_FALLBACK) as resp:
                resp.raise_for_status()
                return float(await resp.text())

async def get_block_height() -> int:
    info = await client.get_mining_info()
    return info.blocks