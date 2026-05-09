from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    server_port: int
    blockchain_dir: str

    model_config = {"env_file": ".env"}


settings = Settings()  # type: ignore[call-arg]
