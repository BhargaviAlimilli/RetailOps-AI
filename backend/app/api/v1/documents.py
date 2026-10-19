import uuid
from pathlib import PurePath
from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, Response, UploadFile
from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.provider import ProviderError
from app.api.dependencies import current_user, get_session
from app.db.models import User
from app.rag import repository, service
from app.rag.embeddings import Embeddings, GeminiEmbeddings
from app.schemas.documents import (
    DocumentDetail,
    DocumentInput,
    DocumentResponse,
    SearchInput,
    SearchResponse,
)

router = APIRouter(prefix="/documents", tags=["documents"])


def get_embeddings(request: Request) -> Embeddings:
    return getattr(request.app.state, "embeddings", None) or GeminiEmbeddings(
        request.app.state.settings
    )


@router.get("", response_model=list[DocumentResponse])
async def list_documents(
    user: Annotated[User, Depends(current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
):
    await repository.expire_processing(session, user.id)
    documents = await repository.documents(session, user.id)
    await session.commit()
    return documents


@router.post("", response_model=DocumentResponse, status_code=201)
async def create_document(
    body: DocumentInput,
    request: Request,
    user: Annotated[User, Depends(current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
    embeddings: Annotated[Embeddings, Depends(get_embeddings)],
):
    try:
        return await service.ingest(
            session, user.id, body, settings=request.app.state.settings, embedder=embeddings
        )
    except ProviderError as error:
        raise HTTPException(503, str(error)) from None


@router.post("/search", response_model=SearchResponse)
async def search_documents(
    body: SearchInput,
    request: Request,
    user: Annotated[User, Depends(current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
    embeddings: Annotated[Embeddings, Depends(get_embeddings)],
):
    try:
        citations = await service.retrieve(
            session,
            user.id,
            body.query,
            body.limit,
            settings=request.app.state.settings,
            embedder=embeddings,
        )
        return SearchResponse(citations=citations)
    except ProviderError as error:
        raise HTTPException(503, str(error)) from None


@router.post("/upload", response_model=DocumentResponse, status_code=201)
async def upload_document(
    request: Request,
    title: Annotated[str, Form(min_length=1, max_length=160)],
    file: Annotated[UploadFile, File()],
    user: Annotated[User, Depends(current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
    embeddings: Annotated[Embeddings, Depends(get_embeddings)],
):
    try:
        suffix = PurePath(file.filename or "").suffix.casefold()
        if suffix not in {".txt", ".md"} or file.content_type not in {
            "text/plain",
            "text/markdown",
            "application/octet-stream",
        }:
            raise HTTPException(
                415, "Upload a UTF-8 .txt or .md file; PDF and binary formats are unsupported"
            )
        data = await file.read(100001)
        if len(data) > 100000:
            raise HTTPException(413, "Document files must be at most 100000 bytes")
        try:
            content = data.decode("utf-8-sig", errors="strict")
            body = DocumentInput(
                title=title, content=content, format="markdown" if suffix == ".md" else "text"
            )
        except (UnicodeDecodeError, ValidationError):
            raise HTTPException(422, "The file must contain valid nonempty UTF-8 text") from None
        try:
            return await service.ingest(
                session, user.id, body, settings=request.app.state.settings, embedder=embeddings
            )
        except ProviderError as error:
            raise HTTPException(503, str(error)) from None
    finally:
        await file.close()


@router.get("/{document_id}", response_model=DocumentDetail)
async def get_document(
    document_id: uuid.UUID,
    user: Annotated[User, Depends(current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
):
    document = await repository.owned(session, user.id, document_id)
    if document is None:
        raise HTTPException(404, "Document not found")
    return document


@router.delete("/{document_id}", status_code=204)
async def delete_document(
    document_id: uuid.UUID,
    user: Annotated[User, Depends(current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> Response:
    await service.delete(session, user.id, document_id)
    return Response(status_code=204)
