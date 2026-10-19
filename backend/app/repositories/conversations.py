import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Conversation, ConversationMessage


async def owned(
    session: AsyncSession,
    user_id: uuid.UUID,
    conversation_id: uuid.UUID,
    *,
    lock: bool = False,
) -> Conversation | None:
    query = select(Conversation).where(
        Conversation.id == conversation_id, Conversation.user_id == user_id
    )
    if lock:
        query = query.with_for_update()
    return await session.scalar(query)


async def conversations(session: AsyncSession, user_id: uuid.UUID) -> list[Conversation]:
    return list(
        await session.scalars(
            select(Conversation)
            .where(Conversation.user_id == user_id)
            .order_by(Conversation.updated_at.desc(), Conversation.id)
            .limit(100)
        )
    )


async def messages(session: AsyncSession, conversation_id: uuid.UUID) -> list[ConversationMessage]:
    return list(
        await session.scalars(
            select(ConversationMessage)
            .where(ConversationMessage.conversation_id == conversation_id)
            .order_by(ConversationMessage.ordinal)
        )
    )


async def request_messages(
    session: AsyncSession, user_id: uuid.UUID, request_id: uuid.UUID
) -> list[ConversationMessage]:
    return list(
        await session.scalars(
            select(ConversationMessage)
            .where(
                ConversationMessage.user_id == user_id, ConversationMessage.request_id == request_id
            )
            .order_by(ConversationMessage.ordinal)
        )
    )


async def lock_user_requests(session: AsyncSession, user_id: uuid.UUID) -> None:
    # A short transaction lock makes request IDs unique across all this user's conversations.
    await session.execute(select(func.pg_advisory_xact_lock(1843, user_id.int % (2**31))))


async def lock_generation_budget(session: AsyncSession) -> None:
    # Two-int advisory namespace is distinct from inventory's bigint lock key space.
    await session.execute(select(func.pg_advisory_xact_lock(1842, 1)))
