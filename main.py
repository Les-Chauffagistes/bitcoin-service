from src.settings import settings
from init import routes, app, log
from aiohttp import web
from src.v1.services.derivation import NetworkMismatch
from asyncio import new_event_loop, set_event_loop, Future, Task, create_task


async def startup_checks():
    from src.modules.db import db
    from src.utils.alerts import alert
    from src.v1.services.invoices import get_deriver

    # Refuse de démarrer : xpub invalide ou d'un autre réseau (ValueError), base injoignable
    deriver = get_deriver()
    await db.connect()
    try:
        await deriver.check_network()
    except NetworkMismatch:
        raise
    except Exception as exc:
        # Nœud injoignable au démarrage : le contrôle est refait avant chaque dérivation
        alert("node_unreachable", "Réseau du nœud non vérifié au démarrage", level="WARNING", error=str(exc))


def start_workers() -> list[Task]:
    from src.modules.bitcoin_cli.instance import rpc, wallet_rpc
    from src.modules.db import db
    from src.v1.services.invoices import get_deriver
    from src.workers.scanner import Scanner

    scanner = Scanner(
        node=rpc,
        wallet=wallet_rpc,
        wallet_name=settings.bitcoin_rpc_wallet,
        db=db,
        deriver=get_deriver(),
        min_confirmations=settings.min_confirmations,
        dust_sats=settings.dust_sats,
        interval_seconds=settings.scan_interval_seconds,
    )
    return [create_task(scanner.run(), name="scanner")]


async def main():
    log.info("Démarrage du serveur...")
    await startup_checks()
    workers = start_workers()  # noqa: F841 (références gardées : une tâche sans référence peut être collectée)
    
    runner = web.AppRunner(app)
    await runner.setup()

    site = web.TCPSite(runner, "0.0.0.0", settings.server_port)
    await site.start()
    log.info(f"Serveur interne en ligne sur localhost:{settings.server_port}")

    await Future()


if __name__ == "__main__":
    from src import v1, health

    app.add_routes(routes)
    loop = new_event_loop()
    set_event_loop(loop)
    try:
        loop.run_until_complete(main())

    except KeyboardInterrupt:
        log.info("Bye")
        exit(0)
