from collections.abc import Awaitable, Callable
from typing import Any

from starlette.responses import JSONResponse


ASGIApp = Callable[[dict[str, Any], Callable[[], Awaitable[dict[str, Any]]], Callable], Awaitable[None]]


class RequestBodyLimitMiddleware:
    def __init__(self, app: ASGIApp, *, path_limits: dict[str, int]) -> None:
        self.app = app
        self.path_limits = path_limits

    async def __call__(self, scope: dict[str, Any], receive: Callable, send: Callable) -> None:
        if scope.get("type") != "http":
            await self.app(scope, receive, send)
            return
        limit = self.path_limits.get(str(scope.get("path", "")))
        if limit is None:
            await self.app(scope, receive, send)
            return

        content_length = _content_length(scope)
        if content_length is not None and content_length > limit:
            await _too_large(scope, receive, send)
            return

        chunks: list[bytes] = []
        total = 0
        while True:
            message = await receive()
            if message.get("type") != "http.request":
                await self.app(scope, _single_message_receiver(message), send)
                return
            body = message.get("body", b"")
            total += len(body)
            if total > limit:
                await _too_large(scope, receive, send)
                return
            chunks.append(body)
            if not message.get("more_body", False):
                break

        replayed = False

        async def replay_receive() -> dict[str, Any]:
            nonlocal replayed
            if replayed:
                return {"type": "http.request", "body": b"", "more_body": False}
            replayed = True
            return {"type": "http.request", "body": b"".join(chunks), "more_body": False}

        await self.app(scope, replay_receive, send)


def _content_length(scope: dict[str, Any]) -> int | None:
    for name, value in scope.get("headers", []):
        if name.lower() != b"content-length":
            continue
        try:
            return int(value)
        except ValueError:
            return None
    return None


def _single_message_receiver(message: dict[str, Any]) -> Callable[[], Awaitable[dict[str, Any]]]:
    async def receive() -> dict[str, Any]:
        return message

    return receive


async def _too_large(scope: dict[str, Any], receive: Callable, send: Callable) -> None:
    response = JSONResponse(status_code=413, content={"detail": "import_request_too_large"})
    await response(scope, receive, send)
