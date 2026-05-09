from src.middlewares.logger import error_handler
from src.middlewares.cors import cors_middleware
from src.modules import logger
from aiohttp.web import Application, RouteTableDef

log = logger.Logger("output.log")

app = Application(
    middlewares=(error_handler,cors_middleware)
)

routes = RouteTableDef()