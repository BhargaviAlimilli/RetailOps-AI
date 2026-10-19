import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.ai.provider import Usage


class ConversationInput(BaseModel):
    title: str = Field(default="New conversation", min_length=1, max_length=120)

    @field_validator("title")
    @classmethod
    def nonblank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Title must not be blank")
        return value.strip()


class ConversationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    title: str
    created_at: datetime
    updated_at: datetime


class MessageInput(BaseModel):
    content: str = Field(min_length=1, max_length=8000)
    request_id: uuid.UUID

    @field_validator("content")
    @classmethod
    def nonblank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Message must not be blank")
        return value


class MessageResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    conversation_id: uuid.UUID
    request_id: uuid.UUID
    role: Literal["user", "assistant"]
    content: str
    status: Literal["pending", "streaming", "completed", "cancelled", "error"]
    created_at: datetime
    updated_at: datetime
    usage: Usage | None
    error_code: str | None
    finish_reason: str | None
