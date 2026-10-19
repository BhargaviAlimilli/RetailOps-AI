"""Explicitly authorized single-call Gemini integration smoke check; never run in CI."""

import argparse
import asyncio
import json
import uuid

from fastapi.testclient import TestClient
from sqlalchemy.engine import make_url

from app.core.config import Settings
from app.main import create_app


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--allow-model-call", action="store_true")
    args = parser.parse_args()
    if not args.allow_model_call:
        parser.error("Explicit --allow-model-call is required after user authorization")
    settings = Settings()
    if (
        not settings.database_url
        or make_url(settings.database_url.get_secret_value()).database != "retailops_demo"
    ):
        parser.error("This check requires the disposable retailops_demo database")
    settings = settings.model_copy(
        update={
            "ai_provider": "gemini",
            "ai_max_output_tokens": 256,
            "ai_max_retries": 0,
            "allowed_hosts": ["testserver"],
        }
    )
    with TestClient(
        create_app(settings), backend_options={"loop_factory": asyncio.SelectorEventLoop}
    ) as client:
        login = client.post(
            "/api/v1/auth/login",
            json={
                "email": "manager@retailops.demo",
                "password": settings.demo_password.get_secret_value(),
            },
        )
        assert login.status_code == 200, "Demo login failed"
        headers = {"Authorization": "Bearer " + login.json()["access_token"]}
        conversation = client.post(
            "/api/v1/conversations", headers=headers, json={"title": "Authorized live Gemini check"}
        )
        assert conversation.status_code == 201, "Conversation creation failed"
        path = f"/api/v1/conversations/{conversation.json()['id']}/messages"
        body = {
            "request_id": str(uuid.uuid4()),
            "content": "Explain safety stock in two sentences. Do not claim store record access.",
        }
        with client.stream("POST", path, headers=headers, json=body) as response:
            assert response.status_code == 200, f"Stream HTTP status {response.status_code}"
            frames = [line[6:] for line in response.iter_lines() if line.startswith("data: ")]
        events = [json.loads(frame) for frame in frames]
        terminal = events[-1]["payload"]
        assert terminal.get("status") == "completed", (
            f"Live generation failed: {terminal.get('code', 'unknown')}"
        )
        assert terminal.get("content"), "No generated text"
        saved = client.get(path, headers=headers).json()
        assert saved[-1]["content"] == terminal["content"], "Saved response differs from stream"
        replay = client.post(path, headers=headers, json=body)
        assert replay.status_code == 200 and terminal["content"] in replay.text, (
            "Idempotent replay failed"
        )
        print(
            json.dumps(
                {
                    "live_stream": "passed",
                    "persisted": True,
                    "replay": True,
                    "frame_count": len(events),
                    "usage": terminal.get("usage"),
                    "finish_reason": terminal.get("finish_reason"),
                }
            )
        )
        client.post("/api/v1/auth/logout", headers=headers)


if __name__ == "__main__":
    main()
