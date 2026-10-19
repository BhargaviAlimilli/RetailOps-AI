from typing import Literal

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel

router = APIRouter(tags=["health"])


class HealthResponse(BaseModel):
    status: Literal["ok", "ready", "unavailable"]
    service: Literal["retailops-api"] = "retailops-api"


@router.get("/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    return HealthResponse(status="ok")


@router.get(
    "/ready",
    response_model=HealthResponse,
    responses={503: {"model": HealthResponse, "description": "Database unavailable"}},
)
async def ready(request: Request) -> JSONResponse:
    available = await request.app.state.database.is_ready()
    body = HealthResponse(status="ready" if available else "unavailable")
    return JSONResponse(status_code=200 if available else 503, content=body.model_dump())
