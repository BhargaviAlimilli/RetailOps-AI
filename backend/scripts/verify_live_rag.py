"""Explicitly authorized, bounded live embedding verification against the local demo only."""

import argparse
import asyncio
import json
import re
import sys
from pathlib import Path

from fastapi.testclient import TestClient
from google import genai
from google.genai import errors, types
from sqlalchemy.engine import make_url

from app.ai.provider import ProviderError
from app.api.v1.documents import get_embeddings, router
from app.core.config import Settings
from app.main import create_app
from app.rag.embeddings import GeminiEmbeddings


async def diagnose(settings):
    client = genai.Client(
        vertexai=False,
        api_key=settings.gemini_api_key.get_secret_value(),
        http_options=types.HttpOptions(
            timeout=30000, retry_options=types.HttpRetryOptions(attempts=1)
        ),
    )
    report = {"model": settings.gemini_embedding_model, "embedding_request_attempts": 0}
    try:
        try:
            metadata = await client.aio.models.get(model=settings.gemini_embedding_model)
            report["metadata"] = {
                "name": metadata.name,
                "supported_actions": metadata.supported_actions,
            }
        except errors.APIError as error:
            report["metadata"] = {"status": error.code}
        report["embedding_request_attempts"] = 1
        response = await client.aio.models.embed_content(
            model=settings.gemini_embedding_model,
            contents=["Synthetic policy: count shelves every Monday."],
            config=types.EmbedContentConfig(
                task_type="RETRIEVAL_DOCUMENT", output_dimensionality=768
            ),
        )
        report["embedding"] = {
            "vectors": len(response.embeddings or []),
            "dimensions": [len(item.values or []) for item in response.embeddings or []],
        }
    except errors.APIError as error:
        message = str(error.message).replace(
            settings.gemini_api_key.get_secret_value(), "[redacted]"
        )
        message = re.sub(r"AIza[A-Za-z0-9_-]+", "[redacted]", message)
        report["error"] = {"status": error.code, "message": message[:500]}
    except Exception as error:
        report["error"] = {"type": type(error).__name__}
    finally:
        await client.aio.aclose()
    print(json.dumps(report, indent=2))


class MeteredEmbeddings(GeminiEmbeddings):
    def __init__(self, settings):
        super().__init__(settings)
        self.request_attempts = 0
        self.last_error = None

    async def embed(self, texts, *, task):
        # Each short fixture/query must fit one SDK request. Never retry or exceed eight requests.
        if len(texts) > self.settings.rag_embedding_batch_size or self.request_attempts >= 8:
            raise ProviderError("ai_rate_limited")
        self.request_attempts += 1
        try:
            return await super().embed(texts, task=task)
        except ProviderError as error:
            source = error.__context__
            self.last_error = {
                "code": error.code,
                "source_type": type(source).__name__ if source else None,
                "source_status": getattr(source, "code", None),
            }
            raise


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--allow-model-calls", action="store_true")
    parser.add_argument("--diagnose-embedding", action="store_true")
    arguments = parser.parse_args()
    if not arguments.allow_model_calls:
        raise SystemExit(
            "Live embedding calls require --allow-model-calls and explicit user authorization."
        )
    settings = Settings()
    if (
        settings.environment != "development"
        or settings.database_url is None
        or make_url(settings.database_url.get_secret_value()).database != "retailops_demo"
    ):
        raise SystemExit(
            "Live verification is restricted to the development retailops_demo database."
        )
    if settings.demo_password is None or settings.gemini_api_key is None:
        raise SystemExit(
            "Configure local demo credentials and Gemini key before live verification."
        )
    if arguments.diagnose_embedding:
        loop_factory = asyncio.SelectorEventLoop if sys.platform == "win32" else None
        with asyncio.Runner(loop_factory=loop_factory) as runner:
            runner.run(diagnose(settings))
        return 0
    settings = settings.model_copy(
        update={"rag_enabled": True, "ai_max_retries": 0, "allowed_hosts": ["testserver"]}
    )
    embeddings = MeteredEmbeddings(settings)
    app = create_app(settings)
    if "/api/v1/documents" not in app.openapi()["paths"]:
        app.include_router(router, prefix="/api/v1")
    app.dependency_overrides[get_embeddings] = lambda: embeddings
    fixture_dir = Path(__file__).parents[1] / "fixtures" / "data" / "documents"
    report = {"embedding_model": settings.gemini_embedding_model, "documents": [], "searches": []}
    options = {"loop_factory": asyncio.SelectorEventLoop} if sys.platform == "win32" else {}
    with TestClient(app, backend_options=options) as client:
        login = client.post(
            "/api/v1/auth/login",
            json={
                "email": "manager@retailops.demo",
                "password": settings.demo_password.get_secret_value(),
            },
        )
        if login.status_code != 200:
            print(
                json.dumps(
                    {
                        "error": "demo_login_failed",
                        "status": login.status_code,
                        "embedding_request_attempts": 0,
                    }
                )
            )
            return 1
        headers = {"Authorization": "Bearer " + login.json()["access_token"]}
        for name in ("stock-counting.md", "supplier-policy.md", "returns-policy.md"):
            response = client.post(
                "/api/v1/documents",
                headers=headers,
                json={
                    "title": name,
                    "content": (fixture_dir / name).read_text(encoding="utf-8"),
                    "format": "markdown",
                },
            )
            report["documents"].append(
                {
                    "title": name,
                    "http_status": response.status_code,
                    "document_id": response.json().get("id"),
                    "status": response.json().get("status"),
                }
            )
            if response.status_code != 201:
                break
        if (
            all(item["http_status"] == 201 for item in report["documents"])
            and len(report["documents"]) == 3
        ):
            for query, expected in (
                ("How often should staff count shelves?", "stock-counting.md"),
                ("What receipt is needed for a refund?", "returns-policy.md"),
            ):
                response = client.post(
                    "/api/v1/documents/search", headers=headers, json={"query": query, "limit": 3}
                )
                citations = response.json().get("citations", [])
                report["searches"].append(
                    {
                        "query": query,
                        "http_status": response.status_code,
                        "top_title": citations[0]["title"] if citations else None,
                        "expected_title": expected,
                        "correct_at_1": bool(citations and citations[0]["title"] == expected),
                    }
                )
                if response.status_code != 200:
                    break
        client.post("/api/v1/auth/logout", headers=headers)
    report["embedding_request_attempts"] = embeddings.request_attempts
    report["last_error"] = embeddings.last_error
    print(json.dumps(report, indent=2))
    return (
        0
        if len(report["searches"]) == 2 and all(item["correct_at_1"] for item in report["searches"])
        else 1
    )


if __name__ == "__main__":
    sys.exit(main())
