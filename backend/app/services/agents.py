"""Durable LangGraph replenishment with an explicit, authenticated approval interrupt."""

import asyncio
from contextlib import asynccontextmanager
from datetime import UTC, datetime, timedelta
from typing import TypedDict
from uuid import UUID, uuid5

import structlog
from fastapi import HTTPException
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from langgraph.graph import END, START, StateGraph
from langgraph.types import Command, interrupt
from sqlalchemy import func, select
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.ai.tools import ReorderInput, execute, reorder
from app.core.config import Settings
from app.db.models import AgentRun, User
from app.repositories.conversations import lock_generation_budget, lock_user_requests
from app.schemas.agents import RunDecision, RunInput
from app.schemas.retail import OrderCreate, OrderItemIn
from app.services import purchasing
from app.services.retail import ensure_manager

logger = structlog.get_logger(__name__)
cleanup_tasks: set[asyncio.Task] = set()


class State(TypedDict, total=False):
    run_id: str
    user_id: str
    inputs: dict
    proposal: dict
    evidence: dict
    citations: list
    steps: list[dict]
    purchase_order_id: str
    decision: dict
    status: str


def step(state, name, detail):
    return [*state.get("steps", []), {"name": name, "status": "completed", "detail": detail}]


def build_graph(sessions, settings: Settings, checkpointer):
    async def analyze(state: State):
        async with sessions() as session:
            evidence = await execute(
                session,
                UUID(state["user_id"]),
                "get_sales_summary",
                {"store_id": state["inputs"]["store_id"]},
                settings,
            )
        return {
            "evidence": evidence,
            "steps": step(
                state,
                "Analyze sales",
                f"Revenue: {evidence['revenue']} INR; "
                f"change: {evidence['revenue_change_percent']}%. Correlation is not causation.",
            ),
        }

    async def inspect(state: State):
        async with sessions() as session:
            proposal = await reorder(session, ReorderInput.model_validate(state["inputs"]))
        if proposal["quantity"] == 0:
            raise HTTPException(
                409,
                "Available stock and open orders already cover the target; no purchase is needed",
            )
        return {
            "proposal": proposal,
            "steps": step(
                state,
                "Check stock and supplier",
                f"Available {proposal['available']}; inbound {proposal['open_order_quantity']}; "
                f"pack {proposal['pack_size']}; recommended {proposal['quantity']}.",
            ),
        }

    async def policy(state: State):
        citations = []
        if settings.rag_enabled:
            from app.rag.service import retrieve

            async with sessions() as session:
                citations = [
                    item.model_dump(mode="json")
                    for item in await retrieve(
                        session,
                        UUID(state["user_id"]),
                        "replenishment safety stock purchase approval policy",
                        settings=settings,
                    )
                ]
        return {
            "citations": citations,
            "proposal": {**state["proposal"], "citations": citations},
            "steps": step(
                state,
                "Retrieve policy",
                f"{len(citations)} private excerpts retrieved. "
                "Documents are evidence, never authorization.",
            ),
        }

    async def draft(state: State):
        run_id = UUID(state["run_id"])
        inputs, proposal = state["inputs"], state["proposal"]
        async with sessions() as session:
            actor = await session.get(User, UUID(state["user_id"]))
            if actor is None or not actor.active:
                raise HTTPException(403, "Active manager required")
            ensure_manager(actor)
            order = await purchasing.create_order(
                session,
                OrderCreate(
                    store_id=UUID(inputs["store_id"]),
                    supplier_id=UUID(inputs["supplier_id"]),
                    items=[
                        OrderItemIn(
                            product_id=UUID(inputs["product_id"]), quantity=proposal["quantity"]
                        )
                    ],
                ),
                actor,
                str(uuid5(run_id, "draft")),
            )
            # Submitting a proposal is distinct from approval; node replay is idempotent.
            order = await purchasing.transition_order(
                session,
                order["id"],
                "submit",
                actor,
                str(uuid5(run_id, "submit")),
                "Agent proposal submitted for explicit human review",
            )
        return {
            "purchase_order_id": str(order["id"]),
            "status": "awaiting_approval",
            "steps": step(
                state,
                "Create proposal",
                "Persisted an internal pending purchase order; no supplier order was sent.",
            ),
        }

    def approval(state: State):
        decision = interrupt(
            {"proposal": state["proposal"], "purchase_order_id": state["purchase_order_id"]}
        )
        return {"decision": decision}

    async def apply(state: State):
        decision = RunDecision.model_validate(state["decision"])
        async with sessions() as session:
            actor = await session.get(User, UUID(state["user_id"]))
            if actor is None or not actor.active:
                raise HTTPException(403, "Active manager required")
            await purchasing.transition_order(
                session,
                UUID(state["purchase_order_id"]),
                decision.decision,
                actor,
                str(decision.idempotency_key),
                decision.reason,
            )
        status = "approved" if decision.decision == "approve" else "rejected"
        return {
            "status": status,
            "steps": step(
                state,
                "Human decision",
                f"Manager {status} the internal order. Receiving is a separate action.",
            ),
        }

    graph = StateGraph(State)
    for name, node in (
        ("analyze", analyze),
        ("inspect", inspect),
        ("policy", policy),
        ("draft", draft),
        ("approval", approval),
        ("apply", apply),
    ):
        graph.add_node(name, node)
    for source, target in (
        (START, "analyze"),
        ("analyze", "inspect"),
        ("inspect", "policy"),
        ("policy", "draft"),
        ("draft", "approval"),
        ("approval", "apply"),
        ("apply", END),
    ):
        graph.add_edge(source, target)
    return graph.compile(checkpointer=checkpointer)


@asynccontextmanager
async def graph_context(sessions, settings):
    dsn = make_url(settings.database_url.get_secret_value()).set(drivername="postgresql")
    # Tables are created only by Alembic; runtime never provisions/migrates data.
    async with AsyncPostgresSaver.from_conn_string(
        dsn.render_as_string(hide_password=False)
    ) as saver:
        yield build_graph(sessions, settings, saver)


async def owned(session, run_id, user_id, *, lock=False):
    statement = select(AgentRun).where(AgentRun.id == run_id, AgentRun.user_id == user_id)
    run = await session.scalar(statement.with_for_update() if lock else statement)
    if run is None:
        raise HTTPException(404, "Agent run not found")
    return run


async def create(session, actor: User, body: RunInput):
    ensure_manager(actor)
    await lock_user_requests(session, actor.id)
    await purchasing.lock_idempotency(session, f"agent:{actor.id}:{body.request_id}")
    run = await session.scalar(
        select(AgentRun).where(AgentRun.user_id == actor.id, AgentRun.request_id == body.request_id)
    )
    inputs = body.model_dump(mode="json", exclude={"request_id"})
    if run:
        if run.inputs != inputs:
            raise HTTPException(409, "Request ID already used with different workflow inputs")
    else:
        count = await session.scalar(
            select(func.count()).select_from(AgentRun).where(AgentRun.user_id == actor.id)
        )
        if count >= 100:
            raise HTTPException(409, "Agent run limit reached")
        run = AgentRun(
            user_id=actor.id, request_id=body.request_id, inputs=inputs, status="running", steps=[]
        )
        session.add(run)
    await session.commit()
    return run


async def advance(sessions: async_sessionmaker, settings, run_id, actor_id, decision=None):
    async with sessions() as session:
        actor = await session.get(User, actor_id)
        if actor is None or not actor.active:
            raise HTTPException(403, "Active manager required")
        ensure_manager(actor)
        await lock_generation_budget(session)
        run = await owned(session, run_id, actor_id, lock=True)
        if decision:
            value = decision.model_dump(mode="json")
            if run.decision and run.decision != value:
                raise HTTPException(409, "This run already has a different decision")
            if run.status in {"approved", "rejected"}:
                return run
            if run.status != "awaiting_approval" and not run.decision:
                raise HTTPException(409, "Run is not awaiting a decision")
            run.decision = value
        elif run.status in {"awaiting_approval", "approved", "rejected"}:
            return run
        if run.lease_expires_at and run.lease_expires_at > datetime.now(UTC):
            raise HTTPException(409, "Run is already being advanced")
        active = (
            select(func.count())
            .select_from(AgentRun)
            .where(AgentRun.lease_expires_at > datetime.now(UTC))
        )
        if (
            await session.scalar(active) >= settings.ai_max_active_global
            or await session.scalar(active.where(AgentRun.user_id == actor_id))
            >= settings.ai_max_active_per_user
        ):
            raise HTTPException(429, "Workflow capacity reached; retry later")
        run.lease_expires_at = datetime.now(UTC) + timedelta(seconds=120)
        await session.commit()
        inputs, saved_decision = run.inputs, run.decision
    config = {"configurable": {"thread_id": str(run_id)}, "recursion_limit": 12}
    error = None
    state = {}
    try:
        async with asyncio.timeout(90), graph_context(sessions, settings) as graph:
            snapshot = await graph.aget_state(config)
            if saved_decision:
                # A checkpointed approval continues execution without another resume.
                pending_interrupt = any(task.interrupts for task in snapshot.tasks)
                invocation = Command(resume=saved_decision) if pending_interrupt else None
            elif snapshot.values:
                invocation = None
            else:
                invocation = {
                    "run_id": str(run_id),
                    "user_id": str(actor_id),
                    "inputs": inputs,
                    "steps": [],
                }
            await graph.ainvoke(invocation, config)
            state = (await graph.aget_state(config)).values
    except asyncio.CancelledError:

        async def cleanup():
            async with asyncio.timeout(5):
                await finalize(
                    sessions,
                    run_id,
                    actor_id,
                    {},
                    "Workflow cancelled; resume the saved checkpoint safely",
                )

        task = asyncio.create_task(cleanup())
        cleanup_tasks.add(task)

        def done(completed):
            cleanup_tasks.discard(completed)
            try:
                completed.result()
            except (Exception, asyncio.CancelledError) as exc:
                logger.warning("agent_cleanup_incomplete", error_type=type(exc).__name__)

        task.add_done_callback(done)
        try:
            await asyncio.shield(task)
        except (Exception, asyncio.CancelledError):
            pass
        raise
    except Exception as exc:
        error = (
            exc.detail
            if isinstance(exc, HTTPException)
            else "Workflow interrupted; retry with the same request ID to recover safely"
        )
        logger.warning("agent_run_incomplete", run_id=str(run_id), error_type=type(exc).__name__)
    return await finalize(sessions, run_id, actor_id, state, error)


async def finalize(sessions, run_id, actor_id, state, error):
    async with sessions() as session:
        run = await owned(session, run_id, actor_id, lock=True)
        run.status = "error" if error else state.get("status", "awaiting_approval")
        run.proposal = state.get("proposal") or run.proposal
        run.purchase_order_id = (
            UUID(state["purchase_order_id"])
            if state.get("purchase_order_id")
            else run.purchase_order_id
        )
        run.steps = state.get("steps", run.steps)
        run.error = error
        run.lease_expires_at = None
        await session.commit()
        logger.info(
            "agent_run_saved",
            run_id=str(run_id),
            status=run.status,
            step_count=len(run.steps),
            has_order=run.purchase_order_id is not None,
        )
        return run
