from os import getenv
from src.middlewares.logger import error_handler
from src.middlewares.cors import cors_middleware
from chauff_cmn.logging import configure, logger as log
from chauff_cmn.logging.aiohttp import request_logging_middleware
from aiohttp.web import Application, RouteTableDef

configure(service="bitcoin-service", level=getenv("LOG_LEVEL", "DEBUG"))

app = Application(
    middlewares=(cors_middleware, request_logging_middleware, error_handler)
)

routes = RouteTableDef()
