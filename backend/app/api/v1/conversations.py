import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.ai.gemini import GeminiProvider
from app.ai.grounded import GroundedProvider
from app.ai.provider import AIProvider, ProviderError
from app.api.dependencies import current_user, get_session
from app.db.models import User
from app.repositories import conversations as repository
from app.schemas.conversations import (
    ConversationInput,
    ConversationResponse,
    MessageInput,
    MessageResponse,
)
from app.services import conversations as service

router = APIRouter(prefix="/conversations", tags=["assistant"])


def get_ai_provider(request: Request) -> AIProvider:
    return getattr(request.app.state, "ai_provider", None) or GeminiProvider(
        request.app.state.settings
    )


@router.post("", response_model=ConversationResponse, status_code=201)
async def create_conversation(
    body: ConversationInput,
    request: Request,
    user: Annotated[User, Depends(current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
):
    return await service.create_conversation(
        session, user.id, body.title, request.app.state.settings
    )


@router.get("", response_model=list[ConversationResponse])
async def list_conversations(
    user: Annotated[User, Depends(current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
):
    return await repository.conversations(session, user.id)


@router.get("/{conversation_id}/messages", response_model=list[MessageResponse])
async def list_messages(
    conversation_id: uuid.UUID,
    user: Annotated[User, Depends(current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
):
    return await service.list_messages(session, user.id, conversation_id)


@router.post("/{conversation_id}/messages")
async def send_message(
    conversation_id: uuid.UUID,
    body: MessageInput,
    request: Request,
    user: Annotated[User, Depends(current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
    provider: Annotated[AIProvider, Depends(get_ai_provider)],
):
    settings = request.app.state.settings
    timeout = settings.ai_timeout_seconds
    sessions = async_sessionmaker(request.app.state.database.engine, expire_on_commit=False)
    # Tests may inject their explicit provider; live Gemini uses bounded read-only grounding.
    if isinstance(provider, GeminiProvider):
        provider = GroundedProvider(provider, sessions, settings, user.id)
    try:
        turn = await service.prepare(
            session, user.id, conversation_id, body, provider, timeout, settings
        )
    except ProviderError as error:
        raise HTTPException(503, str(error)) from None
    return StreamingResponse(
        service.stream_turn(turn, provider, sessions, timeout),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache, no-transform", "X-Accel-Buffering": "no"},
    )
