from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    server_port: int
    bitcoin_rpc_host: str
    bitcoin_rpc_port: int = 8332
    bitcoin_rpc_user: str
    bitcoin_rpc_password: str
    bitcoin_rpc_wallet: str = ""
    bitcoin_network: Literal["main", "testnet4", "regtest"]

    xpub: str
    fee_min_sats: int = 500
    fee_max_sats: int = 20_000
    price_max_age_seconds: int = 1800

    api_token: str = Field(min_length=32)
    database_url: str

    model_config = {"env_file": ".env"}


settings = Settings()  # type: ignore[call-arg]
