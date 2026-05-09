from src.settings import settings
from src.modules.bitcoin_cli.client import Client

client = Client(
    settings.bitcoin_rpc_host,
    settings.bitcoin_rpc_port,
    settings.bitcoin_rpc_user,
    settings.bitcoin_rpc_password,
)


async def get_block_reward() -> float:
    info = await client.get_mining_info()
    era = info.blocks // 210000
    return 50 / (2**era)


async def get_difficulty() -> float:
    info = await client.get_mining_info()
    return info.difficulty