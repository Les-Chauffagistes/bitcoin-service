from pydantic import BaseModel


class MiningInfo(BaseModel):
    blocks: int
    difficulty: float
    networkhashps: float
    pooledtx: int
    chain: str
    warnings: list
