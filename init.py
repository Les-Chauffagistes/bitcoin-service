from os import getenv
from src.middlewares.logger import error_handler
from src.middlewares.cors import cors_middleware
from chauff_cmn.logging import configure, logger as log
from aiohttp.web import Application, RouteTableDef

configure(service="bitcoin-service", level=getenv("LOG_LEVEL", "DEBUG"))

app = Application(
    middlewares=(cors_middleware, error_handler)
)

routes = RouteTableDef()
