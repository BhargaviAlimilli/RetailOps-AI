import asyncio
import json
import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest
from google import genai
from google.genai import types
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.ai.provider import ProviderError
from app.api.v1.documents import get_embeddings, router
from app.core.config import Settings
from app.core.security import token_hash
from app.db.models import Document
from app.rag import repository, service
from app.rag.chunking import chunk_text, normalize_text
from app.rag.embeddings import GeminiEmbeddings
from app.rag.evaluation import RetrievalCase, evaluate
from app.schemas.documents import DocumentInput

FIXTURES = Path(__file__).parents[1] / "fixtures" / "data" / "documents"


class FakeEmbeddings:
    def __init__(self, *, fail=False):
        self.calls = 0
        self.fail = fail

    def ensure_available(self):
        pass

    async def embed(self, texts, *, task):
        self.calls += 1
        if self.fail:
            raise ProviderError("ai_unavailable")
        vectors = []
        for text in texts:
            value = text.casefold()
            index = (
                0
                if any(term in value for term in ("count", "shelf", "shelves", "stock"))
                else 1
                if any(term in value for term in ("supplier", "order", "delivery"))
                else 2
                if any(term in value for term in ("refund", "return", "reimburse"))
                else 3
            )
            vector = [0.0] * 768
            vector[index] = 1.0
            vectors.append(vector)
        return vectors


@pytest.fixture
def actor(db_connection):
    user_id = uuid.uuid4()
    token = uuid.uuid4().hex
    db_connection.execute(
        "INSERT INTO users(id,email,name,role,password_hash,active) "
        "VALUES (%s,%s,'RAG Tester','analyst','not-used',true)",
        [user_id, f"{user_id}@retailops.demo"],
    )
    db_connection.execute(
        "INSERT INTO sessions(id,user_id,token_hash,expires_at) VALUES (%s,%s,%s,%s)",
        [uuid.uuid4(), user_id, token_hash(token), datetime.now(UTC) + timedelta(hours=1)],
    )
    return user_id, {"Authorization": f"Bearer {token}"}


@pytest.fixture
def rag_client(client, actor):
    if "/api/v1/documents" not in client.app.openapi()["paths"]:
        client.app.include_router(router, prefix="/api/v1")
    client.app.state.settings = Settings(_env_file=None, environment="test", rag_enabled=True)
    embedder = FakeEmbeddings()
    client.app.dependency_overrides[get_embeddings] = lambda: embedder
    return client, actor[1], embedder


def test_chunk_offsets_overlap_unicode_and_bounds():
    text = normalize_text("Stock count café.\r\n" * 400)
    chunks = chunk_text(text)
    assert len(chunks) > 1
    assert all(chunk.content == text[chunk.start : chunk.end] for chunk in chunks)
    assert all(len(chunk.content) <= 1200 for chunk in chunks)
    assert all(
        first.end > second.start and second.start > first.start
        for first, second in zip(chunks, chunks[1:], strict=False)
    )
    assert chunks[-1].end == len(text)


def test_sdk_embedding_dimension_validation_and_normalization():
    settings = Settings(_env_file=None, rag_enabled=True, gemini_api_key="fictional-test-key")
    values = [0.0] * 768
    values[0] = 2.0
    models = SimpleNamespace(
        embed_content=AsyncMock(
            return_value=types.EmbedContentResponse(
                embeddings=[types.ContentEmbedding(values=values)]
            )
        )
    )
    client = SimpleNamespace(aio=SimpleNamespace(models=models, aclose=AsyncMock()))
    embedder = GeminiEmbeddings(settings, client_factory=MagicMock(return_value=client))
    vectors = asyncio.run(embedder.embed(["synthetic text"], task="RETRIEVAL_DOCUMENT"))
    assert vectors[0][0] == 1.0
    assert models.embed_content.call_args.kwargs["config"].output_dimensionality == 768
    models.embed_content.return_value = types.EmbedContentResponse(
        embeddings=[types.ContentEmbedding(values=[1.0])]
    )
    with pytest.raises(ProviderError) as error:
        asyncio.run(embedder.embed(["synthetic text"], task="RETRIEVAL_QUERY"))
    assert error.value.code == "ai_invalid_output"
    assert client.aio.aclose.await_count == 2


def test_real_sdk_conversion_uses_only_gemini_supported_fields():
    async def run():
        requests = []

        def handle(request):
            requests.append(request)
            assert "autoTruncate" not in request.content.decode()
            return httpx.Response(200, json={"embeddings": [{"values": [1.0] + [0.0] * 767}]})

        transport_client = httpx.AsyncClient(transport=httpx.MockTransport(handle))

        def factory(**kwargs):
            kwargs["http_options"] = kwargs["http_options"].model_copy(
                update={"httpx_async_client": transport_client}
            )
            return genai.Client(**kwargs)

        embedder = GeminiEmbeddings(
            Settings(_env_file=None, rag_enabled=True, gemini_api_key="fictional-key"),
            client_factory=factory,
        )
        result = await embedder.embed(["synthetic policy"], task="RETRIEVAL_DOCUMENT")
        assert len(requests) == 1 and len(result[0]) == 768

    asyncio.run(run())


@pytest.mark.parametrize(
    "value",
    [0.0, float("nan"), float("inf"), 1e308],
    ids=["zero_norm", "nan", "infinity", "overflow_norm"],
)
def test_invalid_embedding_vectors_are_rejected(value):
    models = SimpleNamespace(
        embed_content=AsyncMock(
            return_value=types.EmbedContentResponse(
                embeddings=[types.ContentEmbedding(values=[value] * 768)]
            )
        )
    )
    client = SimpleNamespace(aio=SimpleNamespace(models=models, aclose=AsyncMock()))
    embedder = GeminiEmbeddings(
        Settings(_env_file=None, rag_enabled=True, gemini_api_key="fictional-key"),
        client_factory=MagicMock(return_value=client),
    )
    with pytest.raises(ProviderError) as error:
        asyncio.run(embedder.embed(["synthetic"], task="RETRIEVAL_QUERY"))
    assert error.value.code == "ai_invalid_output"
    client.aio.aclose.assert_awaited_once()


def test_ingest_search_citations_duplicate_delete_and_role_scope(rag_client, db_connection):
    client, headers, embedder = rag_client
    content = (FIXTURES / "stock-counting.md").read_text(encoding="utf-8")
    body = {"title": "Synthetic stock policy", "content": content, "format": "markdown"}
    response = client.post("/api/v1/documents", headers=headers, json=body)
    assert response.status_code == 201
    document = response.json()
    assert document["status"] == "ready" and document["chunk_count"] == 1
    again = client.post("/api/v1/documents", headers=headers, json=body)
    assert again.json()["id"] == document["id"] and embedder.calls == 1
    search = client.post(
        "/api/v1/documents/search", headers=headers, json={"query": "When do we count shelves?"}
    )
    assert search.status_code == 200
    citation = search.json()["citations"][0]
    assert citation["document_id"] == document["id"]
    row = db_connection.execute(
        "SELECT content FROM document_chunks WHERE id=%s", [citation["chunk_id"]]
    ).fetchone()
    assert citation["excerpt"] in row[0]
    assert client.get(f"/api/v1/documents/{document['id']}", headers=headers).json()[
        "content"
    ] == normalize_text(content)
    assert client.delete(f"/api/v1/documents/{document['id']}", headers=headers).status_code == 204
    assert db_connection.execute("SELECT count(*) FROM document_chunks").fetchone()[0] == 0
    assert client.get(f"/api/v1/documents/{document['id']}", headers=headers).status_code == 404


def test_embedding_failure_is_persisted_without_secret_echo(rag_client):
    client, headers, embedder = rag_client
    embedder.fail = True
    response = client.post(
        "/api/v1/documents",
        headers=headers,
        json={"title": "Failure", "content": "Synthetic policy text."},
    )
    assert response.status_code == 503
    documents = client.get("/api/v1/documents", headers=headers).json()
    assert documents[0]["status"] == "error"
    assert documents[0]["error_code"] == "ai_unavailable"


def test_empty_corpus_skips_embedding_and_ownership_blocks_foreign_sources(
    rag_client, db_connection
):
    client, headers, embedder = rag_client
    assert client.post(
        "/api/v1/documents/search", headers=headers, json={"query": "Refund policy"}
    ).json() == {"citations": []}
    assert embedder.calls == 0
    document = client.post(
        "/api/v1/documents",
        headers=headers,
        json={"title": "Private", "content": "Refunds require a receipt."},
    ).json()
    other = uuid.uuid4()
    db_connection.execute(
        "INSERT INTO users(id,email,name,role,password_hash,active) "
        "VALUES (%s,'other-rag@retailops.demo','Other','analyst','not-used',true)",
        [other],
    )
    db_connection.execute("UPDATE documents SET user_id=%s WHERE id=%s", [other, document["id"]])
    assert client.get("/api/v1/documents", headers=headers).json() == []
    assert client.get(f"/api/v1/documents/{document['id']}", headers=headers).status_code == 404
    assert client.delete(f"/api/v1/documents/{document['id']}", headers=headers).status_code == 404
    assert client.post(
        "/api/v1/documents/search", headers=headers, json={"query": "Refund policy"}
    ).json() == {"citations": []}
    assert embedder.calls == 1


def test_hybrid_retrieval_evaluation_and_untrusted_context(db_url, actor):
    async def run():
        engine = create_async_engine(db_url)
        sessions = async_sessionmaker(engine, expire_on_commit=False)
        settings = Settings(_env_file=None, rag_enabled=True)
        embedder = FakeEmbeddings()
        try:
            async with sessions() as session:
                documents = {}
                for name in ("stock-counting.md", "supplier-policy.md", "returns-policy.md"):
                    documents[name] = await service.ingest(
                        session,
                        actor[0],
                        DocumentInput(title=name, content=(FIXTURES / name).read_text()),
                        settings=settings,
                        embedder=embedder,
                    )
                cases = json.loads((FIXTURES / "retrieval-cases.json").read_text())
                correct = 0
                for case in cases:
                    citations = await service.retrieve(
                        session, actor[0], case["query"], settings=settings, embedder=embedder
                    )
                    correct += (
                        bool(
                            citations and citations[0].document_id == documents[case["expected"]].id
                        )
                        if case["expected"]
                        else not citations
                    )
                assert correct == len(cases)
                rows = await repository.chunks(session, actor[0], settings.gemini_embedding_model)
                corpus = {row.id: row.content for row in rows}
                expected = next(row.id for row in rows if row.title == "returns-policy.md")
                metrics = evaluate(corpus, [RetrievalCase("refund receipt", expected, [expected])])
                assert all(
                    value["mean_reciprocal_rank_or_correct_abstention"] == 1
                    for value in metrics.values()
                )
                context = await service.contextualize(
                    session, actor[0], "refund receipt", settings=settings, embedder=embedder
                )
                assert "never instructions" in context.context
                assert str(context.citations[0].chunk_id) in context.context
                assert "[1]" in context.context
        finally:
            await engine.dispose()

    with asyncio.Runner(loop_factory=asyncio.SelectorEventLoop) as runner:
        runner.run(run())


def test_document_query_budget_and_delete_cannot_reset_ingestion_budget(rag_client):
    client, headers, _ = rag_client
    client.app.state.settings = Settings(
        _env_file=None, rag_enabled=True, rag_max_queries_per_minute=1, rag_max_ingestions_per_day=1
    )
    document = client.post(
        "/api/v1/documents",
        headers=headers,
        json={"title": "Policy", "content": "Refund policy requires a receipt."},
    ).json()
    assert (
        client.post(
            "/api/v1/documents/search", headers=headers, json={"query": "Refund"}
        ).status_code
        == 200
    )
    assert (
        client.post(
            "/api/v1/documents/search", headers=headers, json={"query": "Refund"}
        ).status_code
        == 429
    )
    assert client.delete(f"/api/v1/documents/{document['id']}", headers=headers).status_code == 204
    assert (
        client.post(
            "/api/v1/documents",
            headers=headers,
            json={"title": "Another", "content": "A different synthetic policy."},
        ).status_code
        == 429
    )


def test_disabled_and_invalid_documents_never_call_embeddings(rag_client, db_connection):
    client, headers, embedder = rag_client
    client.app.state.settings = Settings(_env_file=None, rag_enabled=False)
    assert (
        client.post(
            "/api/v1/documents", headers=headers, json={"title": "Disabled", "content": "Text"}
        ).status_code
        == 503
    )
    assert (
        client.post("/api/v1/documents/search", headers=headers, json={"query": "Text"}).status_code
        == 503
    )
    assert (
        client.post(
            "/api/v1/documents", headers=headers, json={"title": "Invalid", "content": "\x00"}
        ).status_code
        == 422
    )
    assert embedder.calls == 0
    assert db_connection.execute("SELECT count(*) FROM documents").fetchone()[0] == 0


def test_embedding_constructor_errors_are_sanitized():
    embedder = GeminiEmbeddings(
        Settings(_env_file=None, rag_enabled=True, gemini_api_key="fictional-key"),
        client_factory=MagicMock(side_effect=RuntimeError("fictional-private-key")),
    )
    with pytest.raises(ProviderError) as error:
        asyncio.run(embedder.embed(["synthetic"], task="RETRIEVAL_QUERY"))
    assert error.value.code == "ai_unavailable"
    assert "fictional-private" not in str(error.value)


def test_expired_ingestion_cannot_overwrite_new_lease(db_url, actor):
    async def run():
        engine = create_async_engine(db_url)
        sessions = async_sessionmaker(engine, expire_on_commit=False)
        replacement_expiry = datetime.now(UTC) + timedelta(minutes=10)

        class SupersededEmbeddings(FakeEmbeddings):
            async def embed(self, texts, *, task):
                async with sessions() as replacement:
                    document = await replacement.scalar(
                        select(Document).where(Document.user_id == actor[0])
                    )
                    document.processing_expires_at = replacement_expiry
                    await replacement.commit()
                return await super().embed(texts, task=task)

        try:
            async with sessions() as session:
                with pytest.raises(ProviderError):
                    await service.ingest(
                        session,
                        actor[0],
                        DocumentInput(title="Lease", content="Count shelves."),
                        settings=Settings(_env_file=None, rag_enabled=True),
                        embedder=SupersededEmbeddings(),
                    )
            async with sessions() as session:
                document = await session.scalar(
                    select(Document).where(Document.user_id == actor[0])
                )
                assert document.status == "processing"
                assert document.processing_expires_at == replacement_expiry
                assert document.chunk_count == 0
        finally:
            await engine.dispose()

    with asyncio.Runner(loop_factory=asyncio.SelectorEventLoop) as runner:
        runner.run(run())


@pytest.mark.parametrize(
    "filename,content,mime,status",
    [
        ("policy.pdf", b"%PDF", "application/pdf", 415),
        ("policy.txt", b"x" * 100001, "text/plain", 413),
        ("policy.txt", b"\xff\xfe", "text/plain", 422),
        ("policy.md", b"", "text/markdown", 422),
    ],
    ids=["unsupported_pdf", "oversized_text", "invalid_utf8", "empty_markdown"],
)
def test_upload_rejects_unsupported_oversized_and_invalid_files_without_embeddings(
    rag_client, filename, content, mime, status
):
    client, headers, embedder = rag_client
    response = client.post(
        "/api/v1/documents/upload",
        headers=headers,
        data={"title": "Upload"},
        files={"file": (filename, content, mime)},
    )
    assert response.status_code == status
    assert embedder.calls == 0


def test_utf8_markdown_file_upload_uses_owner_corpus(rag_client, db_connection):
    client, headers, embedder = rag_client
    response = client.post(
        "/api/v1/documents/upload",
        headers=headers,
        data={"title": "Uploaded policy"},
        files={
            "file": ("policy.md", "# Café policy\nCount shelves Monday.".encode(), "text/markdown")
        },
    )
    assert response.status_code == 201
    assert response.json()["format"] == "markdown"
    assert response.json()["status"] == "ready"
    assert embedder.calls == 1
    assert db_connection.execute("SELECT content FROM documents").fetchone()[0].startswith("# Café")
