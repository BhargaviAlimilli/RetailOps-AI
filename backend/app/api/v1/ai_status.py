"""Expose configuration availability, never credentials or paid health probes."""

from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel

from app.ai.gemini import GeminiProvider
from app.ai.provider import ProviderError
from app.api.dependencies import current_user
from app.db.models import User

router = APIRouter(prefix="/ai", tags=["assistant"])


class AIStatus(BaseModel):
    provider: Literal["disabled", "gemini"]
    configured: bool
    model: str | None
    operational_tools: bool = False


@router.get("/status", response_model=AIStatus)
async def status(request: Request, _user: Annotated[User, Depends(current_user)]) -> AIStatus:
    settings = request.app.state.settings
    try:
        GeminiProvider(settings).ensure_available()
        configured = True
    except ProviderError:
        configured = False
    return AIStatus(provider=settings.ai_provider, configured=configured, model=settings.ai_model)
