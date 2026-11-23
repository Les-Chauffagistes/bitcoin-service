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
os.environ.setdefault("BITCOIN_NETWORK", "regtest")
os.environ.setdefault("API_TOKEN", "test-token-0123456789abcdef0123456789")
os.environ.setdefault("DATABASE_URL", "postgresql://user:password@127.0.0.1:5432/test")
# xpub de test du vecteur BIP84 (réseau main)
os.environ.setdefault(
    "XPUB",
    "xpub6CatWdiZiodmUeTDp8LT5or8nmbKNcuyvz7WyksVFkKB4RHwCD3XyuvPEbvqAQY3rAPshWcMLoP2fMFMKHPJ4ZeZXYVUhLv1VMrjPC7PW6V",
)
os.environ.setdefault("SHOP_WEBHOOK_URL", "http://shop.invalid/api/internal/payments")
os.environ.setdefault("SHOP_WEBHOOK_SECRET", "shop-secret-0123456789abcdef0123456789")


# --- Conteneurs d'intégration (testcontainers) ------------------------------------------------
# Démarrés une seule fois par session, à la première demande ; ignorés si Docker est indisponible.
import base64
import json
import subprocess
import time
import urllib.request
from dataclasses import dataclass

import pytest

ROOT = Path(__file__).resolve().parents[1]
POSTGRES_IMAGE = "postgres:16-alpine"
BITCOIND_IMAGE = "bitcoin/bitcoin:31.2"  # même version que le nœud de production


@dataclass(frozen=True)
class Rpc:
    host: str
    port: int
    user: str
    password: str


def _wait(check, what: str, timeout: float = 90):
    deadline = time.monotonic() + timeout
    while True:
        try:
            if check():
                return
        except Exception:
            pass
        if time.monotonic() > deadline:
            raise TimeoutError(f"{what} n'est pas prêt après {timeout:.0f} s")
        time.sleep(0.5)


@pytest.fixture(scope="session")
def docker_required():
    try:
        import docker

        docker.from_env().ping()
    except Exception as exc:
        pytest.skip(f"Docker indisponible, tests d'intégration ignorés ({exc})")


@pytest.fixture(scope="session")
def postgres_url(docker_required):
    """URL d'un Postgres 16 neuf, migrations Prisma appliquées."""
    from testcontainers.core.container import DockerContainer

    container = (
        DockerContainer(POSTGRES_IMAGE)
        .with_env("POSTGRES_USER", "bitcoin")
        .with_env("POSTGRES_PASSWORD", "bitcoin")
        .with_env("POSTGRES_DB", "bitcoin_service")
        .with_exposed_ports(5432)
    )
    with container:
        # 127.0.0.1 : le serveur temporaire de l'initialisation n'écoute que sur son socket Unix
        _wait(
            lambda: container.exec(["pg_isready", "-h", "127.0.0.1", "-U", "bitcoin", "-d", "bitcoin_service"]).exit_code == 0,
            "Postgres",
        )
        url = (
            f"postgresql://bitcoin:bitcoin@{container.get_container_host_ip()}:"
            f"{container.get_exposed_port(5432)}/bitcoin_service"
        )
        subprocess.run(
            [sys.executable, "-m", "prisma", "migrate", "deploy"],
            cwd=ROOT,
            env={**os.environ, "DATABASE_URL": url},
            check=True,
            capture_output=True,
        )
        yield url


@pytest.fixture(scope="session")
def bitcoind(docker_required):
    """Nœud Bitcoin Core en regtest (même version que la production)."""
    from testcontainers.core.container import DockerContainer

    container = (
        DockerContainer(BITCOIND_IMAGE)
        .with_command(
            "bitcoind -regtest -rpcuser=u -rpcpassword=p -rpcallowip=0.0.0.0/0 -rpcbind=0.0.0.0 "
            "-rpcport=18443 -fallbackfee=0.0002"
        )
        .with_exposed_ports(18443)
    )
    with container:
        rpc = Rpc(container.get_container_host_ip(), int(container.get_exposed_port(18443)), "u", "p")

        def ready() -> bool:
            request = urllib.request.Request(
                f"http://{rpc.host}:{rpc.port}/",
                data=json.dumps({"jsonrpc": "1.0", "id": "t", "method": "getblockchaininfo", "params": []}).encode(),
                headers={"Authorization": "Basic " + base64.b64encode(b"u:p").decode(), "Content-Type": "text/plain"},
            )
            return json.load(urllib.request.urlopen(request, timeout=3))["result"]["chain"] == "regtest"

        _wait(ready, "bitcoind")
        yield rpc
