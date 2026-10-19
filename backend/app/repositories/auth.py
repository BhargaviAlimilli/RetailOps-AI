from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import token_hash
from app.db.models import Session, User


async def user_by_email(session: AsyncSession, email: str) -> User | None:
    return await session.scalar(select(User).where(User.email == email, User.active.is_(True)))


async def authenticated_user(session: AsyncSession, token: str) -> User | None:
    return await session.scalar(
        select(User)
        .join(Session, Session.user_id == User.id)
        .where(
            Session.token_hash == token_hash(token),
            Session.revoked_at.is_(None),
            Session.expires_at > datetime.now(UTC),
            User.active.is_(True),
        )
    )
