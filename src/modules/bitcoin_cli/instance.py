from src.settings import settings

from .client import Client

# Client partagé par les services qui dérivent des adresses et estiment les frais.
rpc = Client(
    settings.bitcoin_rpc_host,
    settings.bitcoin_rpc_port,
    settings.bitcoin_rpc_user,
    settings.bitcoin_rpc_password,
)
