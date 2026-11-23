from functools import wraps
from typing import Awaitable, Callable

from aiohttp.web import Request, StreamResponse, json_response


missing_currency_error = json_response({"error": "invalid payload"}, status=400)


class ApiError(Exception):
    def __init__(self, status: int, code: str, message: str):
        super().__init__(message)
        self.status = status
        self.code = code
        self.message = message


def json_errors(handler: Callable[[Request], Awaitable[StreamResponse]]):
    """Convertit une ApiError en réponse JSON `{ "error": code, "message": … }`."""

    @wraps(handler)
    async def wrapper(request: Request):
        try:
            return await handler(request)
        except ApiError as exc:
            return json_response({"error": exc.code, "message": exc.message}, status=exc.status)

    return wrapper
