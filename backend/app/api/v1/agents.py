from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.api.dependencies import current_user, get_session, require_manager
from app.db.models import AgentRun, User
from app.schemas.agents import RunDecision, RunInput, RunOutput
from app.services import agents as service

router = APIRouter(prefix="/agents/runs", tags=["agents"])
Session = Annotated[AsyncSession, Depends(get_session)]
Actor = Annotated[User, Depends(current_user)]
Manager = Annotated[User, Depends(require_manager)]


@router.get("", response_model=list[RunOutput])
async def list_runs(session: Session, actor: Actor):
    return (
        await session.scalars(
            select(AgentRun)
            .where(AgentRun.user_id == actor.id)
            .order_by(AgentRun.created_at.desc(), AgentRun.id)
            .limit(100)
        )
    ).all()


@router.get("/{run_id}", response_model=RunOutput)
async def get_run(run_id: UUID, session: Session, actor: Actor):
    return await service.owned(session, run_id, actor.id)


@router.post("", response_model=RunOutput)
async def start_run(body: RunInput, request: Request, session: Session, actor: Manager):
    run = await service.create(session, actor, body)
    sessions = async_sessionmaker(request.app.state.database.engine, expire_on_commit=False)
    return await service.advance(sessions, request.app.state.settings, run.id, actor.id)


@router.post("/{run_id}/decision", response_model=RunOutput)
async def decide(run_id: UUID, body: RunDecision, request: Request, actor: Manager):
    sessions = async_sessionmaker(request.app.state.database.engine, expire_on_commit=False)
    return await service.advance(sessions, request.app.state.settings, run_id, actor.id, body)


@router.post("/{run_id}/resume", response_model=RunOutput)
async def resume(run_id: UUID, request: Request, actor: Manager):
    sessions = async_sessionmaker(request.app.state.database.engine, expire_on_commit=False)
    return await service.advance(sessions, request.app.state.settings, run_id, actor.id)
