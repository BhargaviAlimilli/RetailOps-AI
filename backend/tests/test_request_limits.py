import asyncio

from fastapi.testclient import TestClient

from app.core.config import Settings
from app.core.request_limits import RequestLimitsMiddleware
from app.main import create_app


def test_oversized_json_rejected_before_auth_or_parsing():
    with TestClient(create_app(Settings(_env_file=None, allowed_hosts=["testserver"]))) as client:
        response = client.post(
            "/api/v1/documents",
            content=b"x" * 1_048_577,
            headers={"Content-Type": "application/json"},
        )
        assert response.status_code == 413
        assert "x" * 100 not in response.text


def test_chunked_body_cannot_bypass_limit():
    async def run():
        messages = iter(
            [
                {"type": "http.request", "body": b"abcd", "more_body": True},
                {"type": "http.request", "body": b"efgh", "more_body": False},
            ]
        )
        sent = []

        async def receive():
            return next(messages)

        async def send(message):
            sent.append(message)

        async def app(*args):
            raise AssertionError("Oversized input reached parser")

        await RequestLimitsMiddleware(app, maximum_bytes=5)(
            {"type": "http", "method": "POST", "headers": []}, receive, send
        )
        assert sent[0]["status"] == 413

    asyncio.run(run())
