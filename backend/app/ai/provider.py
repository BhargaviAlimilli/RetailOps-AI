"""Application-owned AI contracts. Tool calls are data, never executable code."""

from collections.abc import AsyncIterator
from typing import Literal, Protocol, TypeVar

from pydantic import BaseModel, Field


class AIMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: str


class Usage(BaseModel):
    input_tokens: int = Field(default=0, ge=0)
    output_tokens: int = Field(default=0, ge=0)
    total_tokens: int = Field(default=0, ge=0)


class ToolDefinition(BaseModel):
    name: str = Field(pattern=r"^[A-Za-z_][A-Za-z0-9_]{0,63}$")
    description: str
    parameters: dict


class ToolCall(BaseModel):
    id: str | None = None
    name: str
    arguments: dict


class AIResult(BaseModel):
    text: str
    usage: Usage = Field(default_factory=Usage)
    tool_calls: list[ToolCall] = Field(default_factory=list)
    finish_reason: str | None = None


class AIStreamEvent(BaseModel):
    kind: Literal["text", "tool_call", "usage", "end"]
    text: str = ""
    tool_call: ToolCall | None = None
    usage: Usage | None = None
    finish_reason: str | None = None


class ProviderError(Exception):
    MESSAGES = {
        "ai_disabled": "AI is not configured. Configure an authorized model and key to continue.",
        "ai_timeout": "The AI request exceeded its deadline. Please retry later.",
        "ai_rate_limited": "The AI provider is busy. Please retry later.",
        "ai_unavailable": "The AI provider is temporarily unavailable.",
        "ai_rejected": "The AI provider could not complete this request.",
        "ai_invalid_output": "The AI provider returned an unusable response.",
    }

    def __init__(self, code: str):
        self.code = code
        super().__init__(self.MESSAGES.get(code, self.MESSAGES["ai_unavailable"]))


Structured = TypeVar("Structured", bound=BaseModel)


class AIProvider(Protocol):
    def ensure_available(self) -> None: ...

    async def complete(
        self,
        messages: list[AIMessage],
        *,
        system: str,
        tools: list[ToolDefinition] | None = None,
    ) -> AIResult: ...

    def stream(
        self,
        messages: list[AIMessage],
        *,
        system: str,
        tools: list[ToolDefinition] | None = None,
    ) -> AsyncIterator[AIStreamEvent]: ...

    async def structured(
        self,
        messages: list[AIMessage],
        *,
        system: str,
        schema: type[Structured],
    ) -> Structured: ...
