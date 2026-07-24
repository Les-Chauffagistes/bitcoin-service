import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

# Required at import time by src.settings.Settings()
os.environ.setdefault("SERVER_PORT", "8080")
os.environ.setdefault("BITCOIN_RPC_HOST", "127.0.0.1")
os.environ.setdefault("BITCOIN_RPC_PORT", "8332")
os.environ.setdefault("BITCOIN_RPC_USER", "user")
os.environ.setdefault("BITCOIN_RPC_PASSWORD", "password")
