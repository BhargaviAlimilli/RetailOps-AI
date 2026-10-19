from collections.abc import AsyncIterator
from typing import Annotated

import structlog
from fastapi import Depends, HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.exc import OperationalError
from sqlalchemy.exc import TimeoutError as PoolTimeoutError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.db.models import User
from app.repositories.auth import authenticated_user

bearer = HTTPBearer(auto_error=False)
logger = structlog.get_logger(__name__)


async def get_session(request: Request) -> AsyncIterator[AsyncSession]:
    engine = request.app.state.database.engine
    if engine is None:
        raise HTTPException(503, "Database unavailable")
    try:
        async with async_sessionmaker(engine, expire_on_commit=False)() as session:
            yield session
    except (OperationalError, PoolTimeoutError, TimeoutError, OSError) as error:
        logger.warning("database_unavailable", error_type=type(error).__name__)
        raise HTTPException(503, "Database temporarily unavailable") from None


async def bearer_token(
    credential: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)],
) -> str:
    if (
        credential is None
        or credential.scheme.lower() != "bearer"
        or len(credential.credentials) > 256
    ):
        raise HTTPException(401, "Authentication required", headers={"WWW-Authenticate": "Bearer"})
    return credential.credentials


async def current_user(
    session: Annotated[AsyncSession, Depends(get_session)],
    token: Annotated[str, Depends(bearer_token)],
) -> User:
    user = await authenticated_user(session, token)
    if user is None:
        raise HTTPException(
            401, "Session expired or invalid", headers={"WWW-Authenticate": "Bearer"}
        )
    return user


async def require_manager(user: Annotated[User, Depends(current_user)]) -> User:
    if user.role not in {"admin", "manager"}:
        raise HTTPException(403, "Manager role required")
    return user
