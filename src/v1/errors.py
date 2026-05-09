from aiohttp.web import json_response


missing_currency_error = json_response({"error": "invalid payload"}, status=400)