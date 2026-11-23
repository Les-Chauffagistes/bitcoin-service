from hmac import compare_digest

from aiohttp import web
from aiohttp.web import StreamResponse
from aiohttp.web_request import Request
from typing import Awaitable, Callable
from functools import wraps

from src.settings import settings


def require_auth(handler: Callable[[Request], Awaitable[StreamResponse]]):
    @wraps(handler)
    async def wrapper(request: Request):
        token = request.headers.get("X-Api-Key", "")

        # Temps constant ; encodé en octets pour accepter un en-tête non ASCII sans lever d'exception
        if not compare_digest(token.encode(), settings.api_token.encode()):
            raise web.HTTPUnauthorized()

        return await handler(request)

    return wrapper
