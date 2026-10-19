import secrets
from datetime import UTC, datetime, timedelta

from fastapi import HTTPException
from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth_limits import verify_password_bounded
from app.core.security import hash_password, token_hash
from app.db.models import AuditLog, Session, User
from app.repositories.auth import user_by_email

# Use the same work factor for missing and existing accounts.
DUMMY_HASH = hash_password(secrets.token_urlsafe(32))


async def login(session: AsyncSession, email: str, password: str) -> tuple[str, User]:
    user = await user_by_email(session, email.strip().lower())
    valid = await verify_password_bounded(password, user.password_hash if user else DUMMY_HASH)
    if user is None or not valid:
        raise HTTPException(
            401, "Invalid email or password", headers={"WWW-Authenticate": "Bearer"}
        )
    token = secrets.token_urlsafe(48)
    session.add(
        Session(
            user_id=user.id,
            token_hash=token_hash(token),
            expires_at=datetime.now(UTC) + timedelta(hours=8),
        )
    )
    session.add(
        AuditLog(actor_id=user.id, action="auth.login", entity_type="user", entity_id=user.id)
    )
    await session.commit()
    return token, user


async def logout(session: AsyncSession, token: str, user: User) -> None:
    await session.execute(
        update(Session)
        .where(Session.token_hash == token_hash(token), Session.user_id == user.id)
        .values(revoked_at=datetime.now(UTC))
    )
    session.add(
        AuditLog(actor_id=user.id, action="auth.logout", entity_type="user", entity_id=user.id)
    )
    await session.commit()
