import uuid
from datetime import UTC, datetime

from sqlalchemy import delete, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Document, DocumentChunk


async def lock_budget(session: AsyncSession) -> None:
    await session.execute(select(func.pg_advisory_xact_lock(1844, 1)))


async def expire_processing(session: AsyncSession, user_id: uuid.UUID) -> None:
    await session.execute(
        update(Document)
        .where(
            Document.user_id == user_id,
            Document.status == "processing",
            Document.processing_expires_at <= datetime.now(UTC),
        )
        .values(status="error", error_code="embedding_interrupted", processing_expires_at=None)
    )


async def owned(
    session: AsyncSession, user_id: uuid.UUID, document_id: uuid.UUID, *, lock=False
) -> Document | None:
    query = (
        select(Document)
        .where(Document.id == document_id, Document.user_id == user_id)
        .execution_options(populate_existing=True)
    )
    return await session.scalar(query.with_for_update() if lock else query)


async def documents(session: AsyncSession, user_id: uuid.UUID) -> list[Document]:
    return list(
        await session.scalars(
            select(Document)
            .where(Document.user_id == user_id)
            .order_by(Document.created_at.desc(), Document.id)
            .limit(50)
        )
    )


async def chunks(session: AsyncSession, user_id: uuid.UUID, model: str):
    return (
        await session.execute(
            select(
                DocumentChunk.id, DocumentChunk.document_id, Document.title, DocumentChunk.content
            )
            .join(Document, Document.id == DocumentChunk.document_id)
            .where(
                Document.user_id == user_id,
                Document.status == "ready",
                Document.embedding_model == model,
            )
            .order_by(Document.id, DocumentChunk.ordinal)
        )
    ).all()


async def semantic(
    session: AsyncSession,
    user_id: uuid.UUID,
    model: str,
    vector: list[float],
    maximum_distance: float,
):
    distance = DocumentChunk.embedding.cosine_distance(vector)
    return (
        await session.execute(
            select(DocumentChunk.id, distance.label("distance"))
            .join(Document, Document.id == DocumentChunk.document_id)
            .where(
                Document.user_id == user_id,
                Document.status == "ready",
                Document.embedding_model == model,
                distance <= maximum_distance,
            )
            .order_by(distance, DocumentChunk.id)
            .limit(30)
        )
    ).all()


async def delete_document(session: AsyncSession, user_id: uuid.UUID, document_id: uuid.UUID):
    await session.execute(
        delete(Document).where(Document.id == document_id, Document.user_id == user_id)
    )
