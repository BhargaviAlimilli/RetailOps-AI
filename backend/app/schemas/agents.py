from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class RunInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    store_id: UUID
    product_id: UUID
    supplier_id: UUID
    request_id: UUID


class RunDecision(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    decision: Literal["approve", "reject"]
    reason: str = Field(min_length=5, max_length=500)
    idempotency_key: UUID


class RunOutput(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    status: Literal["running", "awaiting_approval", "approved", "rejected", "error"]
    purchase_order_id: UUID | None
    proposal: dict | None
    steps: list[dict]
    error: str | None
    created_at: datetime
