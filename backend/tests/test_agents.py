import asyncio
from contextlib import asynccontextmanager
from uuid import uuid4

import pytest
from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from test_retail_reporting import retail_data as retail_data

from app.core.config import Settings
from app.db.models import AgentRun, User
from app.schemas.agents import RunInput
from app.services import agents as service
from app.services import purchasing


def inputs(data):
    return {
        "store_id": str(data["store"]),
        "product_id": str(data["product"]),
        "supplier_id": str(data["supplier"]),
        "request_id": str(uuid4()),
    }


@pytest.fixture
def depleted(retail_data, db_connection):
    db_connection.execute(
        "UPDATE inventory_balances SET quantity=0,reserved=0 WHERE id=%s", [retail_data["balance"]]
    )
    return retail_data


def test_durable_interrupt_explicit_approval_and_idempotent_resume(client, depleted, db_connection):
    headers = depleted["headers"]["manager"]
    body = inputs(depleted)
    response = client.post("/api/v1/agents/runs", headers=headers, json=body)
    assert response.status_code == 200, response.text
    run = response.json()
    assert run["status"] == "awaiting_approval", run
    assert run["proposal"]["quantity"] % 3 == 0
    assert run["proposal"]["quantity"] >= 6
    assert len(run["steps"]) == 4
    path = f"/api/v1/agents/runs/{run['id']}"
    assert (
        db_connection.execute(
            "SELECT count(*) FROM checkpoints WHERE thread_id=%s", [run["id"]]
        ).fetchone()[0]
        > 0
    )
    order_id = run["purchase_order_id"]
    assert (
        db_connection.execute(
            "SELECT status FROM purchase_orders WHERE id=%s", [order_id]
        ).fetchone()[0]
        == "pending"
    )
    assert client.post("/api/v1/agents/runs", headers=headers, json=body).json()["id"] == run["id"]
    decision = {
        "decision": "approve",
        "reason": "Reviewed supplier pricing and stock evidence",
        "idempotency_key": str(uuid4()),
    }
    approved = client.post(path + "/decision", headers=headers, json=decision)
    assert approved.status_code == 200, approved.text
    assert approved.json()["status"] == "approved", approved.text
    assert (
        client.post(path + "/decision", headers=headers, json=decision).json()["status"]
        == "approved"
    )
    conflict = {**decision, "decision": "reject", "idempotency_key": str(uuid4())}
    assert client.post(path + "/decision", headers=headers, json=conflict).status_code == 409
    assert (
        db_connection.execute(
            "SELECT count(*) FROM purchase_order_approvals WHERE purchase_order_id=%s", [order_id]
        ).fetchone()[0]
        == 1
    )
    assert (
        db_connection.execute(
            "SELECT quantity FROM inventory_balances WHERE id=%s", [depleted["balance"]]
        ).fetchone()[0]
        == 0
    )


def test_analyst_denial_owner_isolation_and_rejection(client, depleted):
    manager, analyst = depleted["headers"]["manager"], depleted["headers"]["analyst"]
    assert (
        client.post("/api/v1/agents/runs", headers=analyst, json=inputs(depleted)).status_code
        == 403
    )
    run = client.post("/api/v1/agents/runs", headers=manager, json=inputs(depleted)).json()
    path = f"/api/v1/agents/runs/{run['id']}"
    assert client.get(path, headers=analyst).status_code == 404
    decision = {
        "decision": "reject",
        "reason": "Supplier schedule needs further review",
        "idempotency_key": str(uuid4()),
    }
    assert client.post(path + "/decision", headers=analyst, json=decision).status_code == 403
    response = client.post(path + "/decision", headers=manager, json=decision)
    assert response.json()["status"] == "rejected", response.text


def test_crash_after_pending_order_recovers_checkpoint_without_duplicate(
    client, depleted, db_connection, monkeypatch
):
    original = purchasing.transition_order
    failed = False

    async def crash_once(*args, **kwargs):
        nonlocal failed
        result = await original(*args, **kwargs)
        if not failed and args[2] == "submit":
            failed = True
            raise RuntimeError("synthetic process failure after commit")
        return result

    monkeypatch.setattr(purchasing, "transition_order", crash_once)
    headers = depleted["headers"]["manager"]
    body = inputs(depleted)
    run = client.post("/api/v1/agents/runs", headers=headers, json=body).json()
    assert run["status"] == "error"
    resumed = client.post(f"/api/v1/agents/runs/{run['id']}/resume", headers=headers)
    assert resumed.json()["status"] == "awaiting_approval", resumed.text
    assert db_connection.execute("SELECT count(*) FROM purchase_orders").fetchone()[0] == 1
    assert (
        db_connection.execute(
            "SELECT count(*) FROM audit_logs WHERE action='purchase_order.submit'"
        ).fetchone()[0]
        == 1
    )


def test_no_unnecessary_order_and_request_conflict(client, retail_data, db_connection):
    headers = retail_data["headers"]["manager"]
    body = inputs(retail_data)
    result = client.post("/api/v1/agents/runs", headers=headers, json=body).json()
    assert result["status"] == "error"
    assert "already cover" in result["error"]
    assert db_connection.execute("SELECT count(*) FROM purchase_orders").fetchone()[0] == 0
    body["product_id"] = str(retail_data["slow"])
    assert client.post("/api/v1/agents/runs", headers=headers, json=body).status_code == 409


def test_cancel_after_checkpoint_releases_capacity_and_recovers(
    db_url, depleted, db_connection, monkeypatch
):
    original_context = service.graph_context

    async def run():
        engine = create_async_engine(db_url)
        sessions = async_sessionmaker(engine, expire_on_commit=False)
        settings = Settings(_env_file=None, database_url=db_url, ai_max_active_global=1)
        reached = asyncio.Event()

        @asynccontextmanager
        async def block_after_checkpoint(sessions, settings):
            async with original_context(sessions, settings) as graph:

                class Wrapper:
                    aget_state = graph.aget_state

                    async def ainvoke(self, *args):
                        await graph.ainvoke(*args)
                        reached.set()
                        await asyncio.Event().wait()

                yield Wrapper()

        try:
            async with sessions() as session:
                actor = await session.scalar(select(User).where(User.role == "manager"))
                actor_id = actor.id
                first = await service.create(
                    session, actor, RunInput.model_validate(inputs(depleted))
                )
                second = await service.create(
                    session, actor, RunInput.model_validate(inputs(depleted))
                )
            monkeypatch.setattr(service, "graph_context", block_after_checkpoint)
            task = asyncio.create_task(service.advance(sessions, settings, first.id, actor_id))
            await asyncio.wait_for(reached.wait(), timeout=20)
            with pytest.raises(HTTPException) as error:
                await service.advance(sessions, settings, second.id, actor_id)
            assert error.value.status_code == 429
            task.cancel()
            with pytest.raises(asyncio.CancelledError):
                await task
            async with sessions() as session:
                cancelled = await session.get(AgentRun, first.id)
                assert cancelled.lease_expires_at is None
                assert cancelled.status == "error"
            monkeypatch.setattr(service, "graph_context", original_context)
            resumed = await service.advance(sessions, settings, first.id, actor_id)
            assert resumed.status == "awaiting_approval"
        finally:
            await engine.dispose()

    with asyncio.Runner(loop_factory=asyncio.SelectorEventLoop) as runner:
        runner.run(run())
    assert db_connection.execute("SELECT count(*) FROM purchase_orders").fetchone()[0] == 1
