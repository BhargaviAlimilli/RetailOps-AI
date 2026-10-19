import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


class DocumentInput(BaseModel):
    title: str = Field(min_length=1, max_length=160)
    content: str = Field(min_length=1, max_length=100000)
    format: Literal["text", "markdown"] = "text"

    @field_validator("title", "content")
    @classmethod
    def nonblank(cls, value):
        if not value.strip():
            raise ValueError("Document text must not be blank")
        if "\x00" in value:
            raise ValueError("Document text contains an unsupported null character")
        return value


class DocumentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    title: str
    format: Literal["text", "markdown"]
    status: Literal["processing", "ready", "error"]
    chunk_count: int
    created_at: datetime
    error_code: str | None


class DocumentDetail(DocumentResponse):
    content: str


class SearchInput(BaseModel):
    query: str = Field(min_length=1, max_length=2000)
    limit: int = Field(default=5, ge=1, le=10)

    @field_validator("query")
    @classmethod
    def nonblank(cls, value):
        if not value.strip() or "\x00" in value:
            raise ValueError("Search query must contain valid text")
        return value


class Citation(BaseModel):
    document_id: uuid.UUID
    chunk_id: uuid.UUID
    title: str
    excerpt: str
    score: float = Field(ge=0, allow_inf_nan=False)


class SearchResponse(BaseModel):
    citations: list[Citation]


class RAGContext(BaseModel):
    context: str
    citations: list[Citation]
