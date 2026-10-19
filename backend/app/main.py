from contextlib import asynccontextmanager
from time import perf_counter
from uuid import uuid4

import structlog
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.middleware.trustedhost import TrustedHostMiddleware

from app.api.v1.ai_status import router as ai_status_router
from app.api.v1.auth import router as auth_router
from app.api.v1.conversations import router as conversations_router
from app.api.v1.health import router as health_router
from app.api.v1.purchasing import router as purchasing_router
from app.api.v1.retail import router as retail_router
from app.core.config import Settings
from app.core.logging import configure_logging
from app.db.session import Database


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or Settings()
    configure_logging()
    logger = structlog.get_logger(__name__)

    @asynccontextmanager
    async def lifespan(application: FastAPI):
        application.state.database = Database(settings)
        try:
            yield
        finally:
            await application.state.database.close()

    application = FastAPI(
        title="RetailOps AI API",
        version="0.1.0",
        lifespan=lifespan,
        docs_url="/docs" if settings.environment != "production" else None,
        redoc_url=None,
        openapi_url="/openapi.json" if settings.environment != "production" else None,
    )
    application.state.settings = settings
    application.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=False,
        allow_methods=["GET", "POST", "PATCH", "DELETE"],
        allow_headers=["Authorization", "Content-Type", "Idempotency-Key"],
        expose_headers=["X-Request-ID"],
    )
    application.add_middleware(TrustedHostMiddleware, allowed_hosts=settings.allowed_hosts)

    @application.middleware("http")
    async def request_context(request: Request, call_next):
        request_id = str(uuid4())
        started = perf_counter()
        structlog.contextvars.clear_contextvars()
        structlog.contextvars.bind_contextvars(request_id=request_id)
        try:
            response = await call_next(request)
            response.headers["X-Request-ID"] = request_id
            response.headers["X-Content-Type-Options"] = "nosniff"
            logger.info(
                "http_request",
                method=request.method,
                status_code=response.status_code,
                duration_ms=round((perf_counter() - started) * 1000, 2),
            )
            return response
        finally:
            structlog.contextvars.clear_contextvars()

    @application.exception_handler(RequestValidationError)
    async def validation_error(_request: Request, error: RequestValidationError):
        # Pydantic input/context may contain a password or uploaded private text.
        details = [
            {"loc": item["loc"], "msg": item["msg"], "type": item["type"]}
            for item in error.errors()
        ]
        return JSONResponse(status_code=422, content={"detail": details})

    application.include_router(health_router, prefix="/api/v1")
    application.include_router(auth_router, prefix="/api/v1")
    application.include_router(ai_status_router, prefix="/api/v1")
    application.include_router(conversations_router, prefix="/api/v1")
    application.include_router(retail_router, prefix="/api/v1")
    application.include_router(purchasing_router, prefix="/api/v1")
    return application


app = create_app()
