from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    server_port: int
    bitcoin_rpc_host: str
    bitcoin_rpc_port: int = 8332
    bitcoin_rpc_user: str
    bitcoin_rpc_password: str

    model_config = {"env_file": ".env"}


settings = Settings()  # type: ignore[call-arg]
