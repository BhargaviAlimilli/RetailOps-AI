import asyncio
import json
import uuid
from datetime import UTC, datetime, timedelta

import pytest
from fastapi import HTTPException
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.ai.provider import AIStreamEvent, ProviderError, Usage
from app.api.v1.conversations import get_ai_provider, router
from app.core.config import Settings
from app.core.security import token_hash
from app.db.models import Conversation, ConversationMessage
from app.schemas.conversations import MessageInput
from app.services import conversations as service


class MockProvider:
    def __init__(self, *, failure=False, disabled=False):
        self.failure = failure
        self.disabled = disabled
        self.calls = 0
        self.closed = False
        self.history = None

    def ensure_available(self):
        if self.disabled:
            raise ProviderError("ai_disabled")

    async def stream(self, messages, *, system, tools=None):
        self.calls += 1
        self.history = messages
        assert "NO operational data access" in system
        assert tools is None
        try:
            yield AIStreamEvent(kind="text", text="Operational tools ")
            if self.failure:
                raise RuntimeError("fictional-private-provider-credential")
            yield AIStreamEvent(kind="text", text="are not available yet.")
            yield AIStreamEvent(
                kind="usage", usage=Usage(input_tokens=8, output_tokens=6, total_tokens=14)
            )
            yield AIStreamEvent(kind="end", finish_reason="STOP")
        finally:
            self.closed = True


@pytest.fixture
def actor(db_connection):
    user_id = uuid.uuid4()
    token = uuid.uuid4().hex
    db_connection.execute(
        "INSERT INTO users(id,email,name,role,password_hash,active) "
        "VALUES (%s,%s,'AI Tester','analyst','not-used',true)",
        [user_id, f"{user_id}@retailops.demo"],
    )
    db_connection.execute(
        "INSERT INTO sessions(id,user_id,token_hash,expires_at) VALUES (%s,%s,%s,%s)",
        [uuid.uuid4(), user_id, token_hash(token), datetime.now(UTC) + timedelta(hours=1)],
    )
    return user_id, {"Authorization": f"Bearer {token}"}


@pytest.fixture
def ai_client(client, actor):
    if "/api/v1/conversations" not in client.app.openapi()["paths"]:
        client.app.include_router(router, prefix="/api/v1")
    # Tests also work before application root wiring is committed.
    if not hasattr(client.app.state, "settings"):
        client.app.state.settings = Settings(_env_file=None, environment="test")
    provider = MockProvider()
    client.app.dependency_overrides[get_ai_provider] = lambda: provider
    return client, actor[1], provider


def parse_sse(text):
    events = []
    for block in text.strip().split("\n\n"):
        fields = dict(line.split(": ", 1) for line in block.splitlines())
        events.append((fields["id"], fields["event"], json.loads(fields["data"])))
    return events


def create(client, headers):
    response = client.post(
        "/api/v1/conversations", headers=headers, json={"title": "Synthetic conversation"}
    )
    assert response.status_code == 201
    return response.json()["id"]


def test_conversation_ownership_and_disabled_no_message_writes(ai_client, db_connection):
    client, headers, provider = ai_client
    conversation_id = create(client, headers)
    assert client.get("/api/v1/conversations", headers=headers).json()[0]["id"] == conversation_id
    provider.disabled = True
    response = client.post(
        f"/api/v1/conversations/{conversation_id}/messages",
        headers=headers,
        json={"content": "What are sales?", "request_id": str(uuid.uuid4())},
    )
    assert response.status_code == 503
    assert db_connection.execute("SELECT count(*) FROM conversation_messages").fetchone()[0] == 0
    unknown = uuid.uuid4()
    assert (
        client.get(f"/api/v1/conversations/{unknown}/messages", headers=headers).status_code == 404
    )
    other_user = uuid.uuid4()
    db_connection.execute(
        "INSERT INTO users(id,email,name,role,password_hash,active) "
        "VALUES (%s,'other@retailops.demo','Other','analyst','not-used',true)",
        [other_user],
    )
    db_connection.execute(
        "UPDATE conversations SET user_id=%s WHERE id=%s", [other_user, conversation_id]
    )
    assert (
        client.get(f"/api/v1/conversations/{conversation_id}/messages", headers=headers).status_code
        == 404
    )


def test_stream_persistence_order_usage_and_idempotent_replay(ai_client, db_connection):
    client, headers, provider = ai_client
    conversation_id = create(client, headers)
    body = {"content": "Explain retail sales", "request_id": str(uuid.uuid4())}
    response = client.post(
        f"/api/v1/conversations/{conversation_id}/messages", headers=headers, json=body
    )
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")
    events = parse_sse(response.text)
    assert [event[1] for event in events] == [
        "message.started",
        "message.delta",
        "message.delta",
        "message.completed",
    ]
    assert [event[2]["sequence"] for event in events] == [1, 2, 3, 4]
    assert len({event[0] for event in events}) == 4
    assert events[-1][2]["payload"]["usage"]["total_tokens"] == 14
    assert events[-1][2]["payload"]["finish_reason"] == "STOP"
    messages = client.get(
        f"/api/v1/conversations/{conversation_id}/messages", headers=headers
    ).json()
    assert [message["role"] for message in messages] == ["user", "assistant"]
    assert messages[1]["status"] == "completed"
    assert messages[1]["content"] == events[-1][2]["payload"]["content"]
    assert provider.closed and provider.calls == 1
    replay = client.post(
        f"/api/v1/conversations/{conversation_id}/messages", headers=headers, json=body
    )
    assert parse_sse(replay.text)[-1][2]["message_id"] == messages[1]["id"]
    assert provider.calls == 1
    assert db_connection.execute("SELECT count(*) FROM conversation_messages").fetchone()[0] == 2
    mismatch = client.post(
        f"/api/v1/conversations/{conversation_id}/messages",
        headers=headers,
        json={**body, "content": "different"},
    )
    assert mismatch.status_code == 409


def test_network_failure_preserves_partial_and_sanitizes(ai_client):
    client, headers, provider = ai_client
    provider.failure = True
    conversation_id = create(client, headers)
    response = client.post(
        f"/api/v1/conversations/{conversation_id}/messages",
        headers=headers,
        json={"content": "Question", "request_id": str(uuid.uuid4())},
    )
    assert "fictional-private" not in response.text
    final = parse_sse(response.text)[-1]
    assert final[1] == "message.error"
    assert final[2]["payload"]["code"] == "ai_unavailable"
    messages = client.get(
        f"/api/v1/conversations/{conversation_id}/messages", headers=headers
    ).json()
    assert messages[-1]["status"] == "error"
    assert messages[-1]["content"] == "Operational tools "
    assert provider.closed


@pytest.mark.parametrize("stop_after", [1, 2])
def test_stream_close_at_first_frame_or_partial_cancels_and_releases_lease(
    db_url, db_connection, actor, stop_after
):
    async def run():
        engine = create_async_engine(db_url)
        sessions = async_sessionmaker(engine, expire_on_commit=False)
        provider = MockProvider()
        try:
            async with sessions() as session:
                conversation = await service.create_conversation(
                    session, actor[0], "Cancel", Settings(_env_file=None)
                )
                turn = await service.prepare(
                    session,
                    actor[0],
                    conversation.id,
                    MessageInput(content="Question", request_id=uuid.uuid4()),
                    provider,
                    10,
                )
            iterator = service.stream_turn(turn, provider, sessions, 10)
            for _ in range(stop_after):
                await anext(iterator)
            await iterator.aclose()
            async with sessions() as session:
                stored = await session.get(ConversationMessage, turn.assistant_id)
                conversation = await session.get(Conversation, turn.conversation_id)
                assert stored.status == "cancelled"
                assert stored.content == ("Operational tools " if stop_after == 2 else "")
                assert conversation.active_request_id is None
            assert provider.closed if stop_after == 2 else provider.calls == 0
        finally:
            await engine.dispose()

    with asyncio.Runner(loop_factory=asyncio.SelectorEventLoop) as runner:
        runner.run(run())


def test_concurrent_conversation_capacity_and_generation_budget(db_url, actor):
    async def run():
        engine = create_async_engine(db_url)
        sessions = async_sessionmaker(engine, expire_on_commit=False)
        settings = Settings(
            _env_file=None, ai_max_active_per_user=1, ai_max_generations_per_minute=1
        )
        try:
            async with sessions() as session:
                first = await service.create_conversation(session, actor[0], "First", settings)
                second = await service.create_conversation(session, actor[0], "Second", settings)

            async def reserve(conversation):
                async with sessions() as session:
                    try:
                        return await service.prepare(
                            session,
                            actor[0],
                            conversation.id,
                            MessageInput(content="Question", request_id=uuid.uuid4()),
                            MockProvider(),
                            10,
                            settings,
                        )
                    except HTTPException as error:
                        return error.status_code

            results = await asyncio.gather(reserve(first), reserve(second))
            assert sum(result == 429 for result in results) == 1
            turn = next(result for result in results if result != 429)
            await service.save(sessions, turn, "", "cancelled", Usage())
            async with sessions() as session:
                with pytest.raises(HTTPException) as error:
                    await service.prepare(
                        session,
                        actor[0],
                        second.id,
                        MessageInput(content="New question", request_id=uuid.uuid4()),
                        MockProvider(),
                        10,
                        settings,
                    )
                assert error.value.status_code == 429
        finally:
            await engine.dispose()

    with asyncio.Runner(loop_factory=asyncio.SelectorEventLoop) as runner:
        runner.run(run())


def test_conversation_cap_and_history_bound(ai_client):
    client, headers, _ = ai_client
    client.app.state.settings = Settings(_env_file=None, ai_max_conversations_per_user=1)
    create(client, headers)
    assert client.post("/api/v1/conversations", headers=headers, json={}).status_code == 409
    messages = [
        ConversationMessage(
            role="user" if i % 2 == 0 else "assistant", status="completed", content="x" * 2000
        )
        for i in range(40)
    ]
    history = service.bounded_history(messages)
    assert len(history) <= 20
    assert sum(len(message.content) for message in history) <= 24000


def test_terminal_cleanup_retains_and_consumes_late_failure(monkeypatch, caplog):
    async def run():
        started, release = asyncio.Event(), asyncio.Event()

        async def delayed_save(*args, **kwargs):
            started.set()
            await release.wait()
            raise RuntimeError("fictional-private-cleanup-credential")

        monkeypatch.setattr(service, "save", delayed_save)
        task = asyncio.create_task(
            service.terminal_save(None, None, "partial", "cancelled", Usage(), "cancelled")
        )
        await started.wait()
        task.cancel()
        await task
        assert service.cleanup_tasks
        retained = list(service.cleanup_tasks)
        release.set()
        await asyncio.gather(*retained, return_exceptions=True)
        assert not service.cleanup_tasks

    asyncio.run(run())
    assert "fictional-private" not in caplog.text


def test_daily_generation_allowance_survives_completed_streams(db_url, actor):
    async def run():
        engine = create_async_engine(db_url)
        sessions = async_sessionmaker(engine, expire_on_commit=False)
        settings = Settings(_env_file=None, ai_max_generations_per_day=1)
        try:
            async with sessions() as session:
                conversation = await service.create_conversation(
                    session, actor[0], "Daily cap", settings
                )
                turn = await service.prepare(
                    session,
                    actor[0],
                    conversation.id,
                    MessageInput(content="First", request_id=uuid.uuid4()),
                    MockProvider(),
                    10,
                    settings,
                )
            await service.save(sessions, turn, "Reply", "completed", Usage())
            async with sessions() as session:
                with pytest.raises(HTTPException) as error:
                    await service.prepare(
                        session,
                        actor[0],
                        conversation.id,
                        MessageInput(content="Second", request_id=uuid.uuid4()),
                        MockProvider(),
                        10,
                        settings,
                    )
                assert error.value.status_code == 429
        finally:
            await engine.dispose()

    with asyncio.Runner(loop_factory=asyncio.SelectorEventLoop) as runner:
        runner.run(run())


def test_global_active_budget_is_shared_across_users(db_url, db_connection, actor):
    other_user = uuid.uuid4()
    db_connection.execute(
        "INSERT INTO users(id,email,name,role,password_hash,active) "
        "VALUES (%s,'global@retailops.demo','Other','analyst','not-used',true)",
        [other_user],
    )

    async def run():
        engine = create_async_engine(db_url)
        sessions = async_sessionmaker(engine, expire_on_commit=False)
        settings = Settings(_env_file=None, ai_max_active_global=1)
        try:
            async with sessions() as session:
                first = await service.create_conversation(session, actor[0], "First", settings)
                second = await service.create_conversation(session, other_user, "Second", settings)

            async def reserve(user_id, conversation_id):
                async with sessions() as session:
                    try:
                        return await service.prepare(
                            session,
                            user_id,
                            conversation_id,
                            MessageInput(content="Question", request_id=uuid.uuid4()),
                            MockProvider(),
                            10,
                            settings,
                        )
                    except HTTPException as error:
                        return error.status_code

            results = await asyncio.gather(
                reserve(actor[0], first.id), reserve(other_user, second.id)
            )
            assert sum(result == 429 for result in results) == 1
        finally:
            await engine.dispose()

    with asyncio.Runner(loop_factory=asyncio.SelectorEventLoop) as runner:
        runner.run(run())


def test_stream_deadline_persists_partial_error_and_closes(db_url, actor):
    class BlockedProvider(MockProvider):
        async def stream(self, messages, *, system, tools=None):
            try:
                yield AIStreamEvent(kind="text", text="partial")
                await asyncio.Event().wait()
            finally:
                self.closed = True

    async def run():
        engine = create_async_engine(db_url)
        sessions = async_sessionmaker(engine, expire_on_commit=False)
        provider = BlockedProvider()
        try:
            async with sessions() as session:
                conversation = await service.create_conversation(
                    session, actor[0], "Deadline", Settings(_env_file=None)
                )
                turn = await service.prepare(
                    session,
                    actor[0],
                    conversation.id,
                    MessageInput(content="Question", request_id=uuid.uuid4()),
                    provider,
                    1,
                )
            frames = [frame async for frame in service.stream_turn(turn, provider, sessions, 0.05)]
            assert parse_sse(frames[-1])[0][2]["payload"]["code"] == "ai_timeout"
            async with sessions() as session:
                stored = await session.get(ConversationMessage, turn.assistant_id)
                assert stored.status == "error" and stored.content == "partial"
            assert provider.closed
        finally:
            await engine.dispose()

    with asyncio.Runner(loop_factory=asyncio.SelectorEventLoop) as runner:
        runner.run(run())
