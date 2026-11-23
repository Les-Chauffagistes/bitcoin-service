from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    server_port: int
    bitcoin_rpc_host: str
    bitcoin_rpc_port: int = 8332
    bitcoin_rpc_user: str
    bitcoin_rpc_password: str
    bitcoin_rpc_wallet: str = "bitcoin-service"
    bitcoin_network: Literal["main", "testnet4", "regtest"]

    xpub: str
    fee_min_sats: int = 500
    fee_max_sats: int = 20_000
    price_max_age_seconds: int = 1800

    min_confirmations: int = Field(default=3, ge=1)
    scan_interval_seconds: int = Field(default=15, ge=1)
    dust_sats: int = 1_000

    shop_webhook_url: str
    shop_webhook_secret: str = Field(min_length=32)
    webhook_timeout_seconds: float = 10
    sender_interval_seconds: float = 2

    api_token: str = Field(min_length=32)
    database_url: str

    model_config = {"env_file": ".env"}


settings = Settings()  # type: ignore[call-arg]
