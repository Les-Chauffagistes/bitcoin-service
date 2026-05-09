from src.settings import settings
from src.modules.bitcoin_cli.client import Client

client = Client(settings.blockchain_dir)


def get_block_reward():
    info = client.get_mining_info()
    height = info.blocks
    ERA = height // 210000
    return 50 / (2**ERA)


def get_difficulty():
    info = client.get_mining_info()
    return info.difficulty