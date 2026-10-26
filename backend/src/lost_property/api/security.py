import json
import logging
import time
from collections import deque
from threading import Lock
from uuid import uuid4

from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from lost_property.application.service import AppError
from lost_property.config import Settings

COOKIE = "riverside_session"
logger = logging.getLogger("riverside.requests")


class Limiter:
    def __init__(self) -> None:
        self.buckets: dict[str, deque[float]] = {}
        self.lock = Lock()

    def take(self, key: str, maximum: int, seconds: int) -> None:
        now = time.monotonic()
        with self.lock:
            for expired in [
                name
                for name, values in self.buckets.items()
                if not values or values[-1] <= now - 600
            ]:
                del self.buckets[expired]
            if key not in self.buckets and len(self.buckets) >= 4096:
                raise AppError(429, "RATE_LIMIT", "The service is busy. Please try again later.")
            values = self.buckets.setdefault(key, deque())
            while values and values[0] <= now - seconds:
                values.popleft()
            if len(values) >= maximum:
                raise AppError(429, "RATE_LIMIT", "Too many requests. Please try again shortly.")
            values.append(now)


class SecurityMiddleware:
    def __init__(self, app: ASGIApp, settings: Settings) -> None:
        self.app, self.settings = app, settings

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        identity, started = str(uuid4()), time.perf_counter()
        scope.setdefault("state", {})["request_id"] = identity
        headers = dict(scope["headers"])
        status = 500

        async def safe_send(message: Message) -> None:
            nonlocal status
            if message["type"] == "http.response.start":
                status = message["status"]
                extra = [
                    (b"x-content-type-options", b"nosniff"),
                    (b"x-frame-options", b"DENY"),
                    (b"referrer-policy", b"no-referrer"),
                    (b"x-request-id", identity.encode()),
                    (
                        b"content-security-policy",
                        b"default-src 'self'; script-src 'self'; style-src 'self'; "
                        b"font-src 'self'; img-src 'self' data:; connect-src 'self'; "
                        b"frame-ancestors 'none'",
                    ),
                ]
                if scope["path"].startswith("/api/"):
                    extra.append((b"cache-control", b"no-store"))
                if self.settings.secure_cookies:
                    extra.append((b"strict-transport-security", b"max-age=31536000"))
                message["headers"] = list(message.get("headers", [])) + extra
            await send(message)

        async def reject(code: int, name: str, message: str) -> None:
            await JSONResponse(
                {"error": {"code": name, "message": message, "request_id": identity}},
                status_code=code,
            )(scope, receive, safe_send)

        try:
            if scope["method"] in ("POST", "DELETE", "PUT", "PATCH"):
                origin = headers.get(b"origin", b"").decode("latin-1")
                if origin not in self.settings.allowed_origins:
                    await reject(403, "ORIGIN_REJECTED", "Use this service from its own website.")
                    return
                chunks: list[bytes] = []
                size = 0
                audio_request = scope["path"] == "/api/v1/transcriptions"
                maximum = self.settings.audio_max_bytes if audio_request else 16 * 1024
                while True:
                    message = await receive()
                    if message["type"] == "http.disconnect":
                        return
                    chunk = message.get("body", b"")
                    size += len(chunk)
                    if size > maximum:
                        await reject(413, "BODY_TOO_LARGE", "The request is too large.")
                        return
                    chunks.append(chunk)
                    if not message.get("more_body", False):
                        break
                if (
                    not audio_request
                    and size
                    and not headers.get(b"content-type", b"")
                    .lower()
                    .startswith(b"application/json")
                ):
                    await reject(422, "INVALID_CONTENT_TYPE", "Send a JSON request.")
                    return
                consumed = False

                async def replay() -> Message:
                    nonlocal consumed
                    if not consumed:
                        consumed = True
                        return {
                            "type": "http.request",
                            "body": b"".join(chunks),
                            "more_body": False,
                        }
                    return await receive()

                await self.app(scope, replay, safe_send)
            else:
                await self.app(scope, receive, safe_send)
        finally:
            logger.info(
                json.dumps(
                    {
                        "request_id": identity,
                        "method": scope["method"],
                        "path": scope["path"],
                        "status": status,
                        "duration_ms": round((time.perf_counter() - started) * 1000, 2),
                    }
                )
            )
