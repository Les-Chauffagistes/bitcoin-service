from src.modules.bitcoin_cli.client import Client

client = Client("/Volumes/Bitcoin")

print(client.get_mining_info())