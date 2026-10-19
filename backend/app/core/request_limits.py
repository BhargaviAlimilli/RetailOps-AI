"""Bound request bodies before JSON/multipart parsing; SSE responses remain unbuffered."""

import asyncio

from starlette.responses import JSONResponse


class RequestLimitsMiddleware:
    def __init__(self, app, maximum_bytes=1_048_576):
        self.app, self.maximum_bytes = app, maximum_bytes

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http" or scope["method"] not in {"POST", "PUT", "PATCH"}:
            return await self.app(scope, receive, send)
        headers = dict(scope.get("headers", []))
        try:
            declared = int(headers.get(b"content-length", b"0"))
        except ValueError:
            declared = self.maximum_bytes + 1
        if declared < 0 or declared > self.maximum_bytes:
            return await JSONResponse({"detail": "Request body exceeds 1 MiB"}, 413)(
                scope, receive, send
            )
        body = bytearray()
        try:
            async with asyncio.timeout(10):
                while True:
                    message = await receive()
                    if message["type"] == "http.disconnect":
                        return
                    data = message.get("body", b"")
                    if len(body) + len(data) > self.maximum_bytes:
                        return await JSONResponse({"detail": "Request body exceeds 1 MiB"}, 413)(
                            scope, receive, send
                        )
                    body.extend(data)
                    if not message.get("more_body", False):
                        break
        except TimeoutError:
            return await JSONResponse({"detail": "Request body deadline exceeded"}, 408)(
                scope, receive, send
            )
        delivered = False

        async def replay():
            nonlocal delivered
            if not delivered:
                delivered = True
                return {"type": "http.request", "body": bytes(body), "more_body": False}
            return await receive()

        await self.app(scope, replay, send)
