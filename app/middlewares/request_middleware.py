"""Trazabilidad sin registrar cuerpos, contraseñas ni tokens."""
import logging
import re
from time import perf_counter
from uuid import uuid4

from slowapi import Limiter
from slowapi.util import get_remote_address
from starlette.datastructures import Headers, MutableHeaders

from app.config import settings

limiter = Limiter(key_func=get_remote_address)
logger = logging.getLogger("uvicorn.error.requests")


class RequestMiddleware:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)
        start = perf_counter()
        incoming = Headers(scope=scope).get("X-Request-ID", "")
        request_id = incoming if re.fullmatch(r"[A-Za-z0-9._:-]{1,128}", incoming) else str(uuid4())
        code = 500

        async def send_with_headers(message):
            nonlocal code
            if message["type"] == "http.response.start":
                code = message["status"]
                headers = MutableHeaders(scope=message)
                headers["X-Process-Time"] = f"{perf_counter() - start:.6f}"
                headers["X-App-Name"] = "device_systems"
                headers["X-API-Version"] = settings.APP_VERSION
                headers["X-Request-ID"] = request_id
            await send(message)

        try:
            await self.app(scope, receive, send_with_headers)
        finally:
            logger.info("method=%s path=%r status=%s request_id=%s duration=%.6f",
                        scope["method"], scope["path"], code, request_id, perf_counter() - start)
