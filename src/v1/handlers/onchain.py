from aiohttp.web import Request, json_response

from ..services import onchain
from ..app import routes



@routes.get("/bitcoin-blockchain-difficulty")
async def get_difficulty(_: Request):
    return json_response(onchain.get_difficulty())

@routes.get("/bitcoin-block-reward")
async def get_block_reward(_: Request):
    return json_response(onchain.get_block_reward())