from aiohttp.web import middleware, StreamResponse, Response
from aiohttp.web_request import Request
from typing import Awaitable, Callable


@middleware
async def cors_middleware(request: Request, handler: Callable[[Request], Awaitable[StreamResponse]]) -> StreamResponse:
    allowed_origins = {
        "https://heatboard.chauffagistes-btc.fr",
    }

    if request.method == "OPTIONS":
        response = Response(status=204)
    else:
        response = await handler(request)

    origin = request.headers.get("Origin")

    if origin in allowed_origins:
        response.headers["Access-Control-Allow-Origin"] = origin
        response.headers["Vary"] = "Origin"
        response.headers["Access-Control-Allow-Credentials"] = "true"
        response.headers["Access-Control-Allow-Headers"] = "Content-Type, Authorization, X-Requested-With"
        response.headers["Access-Control-Allow-Methods"] = "GET, POST, PUT, PATCH, DELETE, OPTIONS"

    return response
