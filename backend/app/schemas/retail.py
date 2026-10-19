"""Validated retail API contracts. Decimal values serialize as strings."""

from datetime import date, datetime
from decimal import Decimal
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator


class Page[T](BaseModel):
    items: list[T]
    total: int
    page: int
    page_size: int


class StoreOut(BaseModel):
    id: UUID
    name: str
    code: str


class CategoryOut(BaseModel):
    id: UUID
    name: str


class ProductOut(BaseModel):
    id: UUID
    sku: str
    name: str
    category_id: UUID
    category_name: str
    unit_cost: Decimal
    unit_price: Decimal


class ProductCreate(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    sku: str = Field(min_length=1, max_length=50, pattern=r"^[A-Za-z0-9_-]+$")
    name: str = Field(min_length=1, max_length=160)
    category_id: UUID
    unit_cost: Decimal = Field(ge=0, max_digits=12, decimal_places=2)
    unit_price: Decimal = Field(ge=0, max_digits=12, decimal_places=2)
    reorder_point: int = Field(default=10, ge=0, le=1000000, strict=True)


class SupplierTerm(BaseModel):
    product_id: UUID
    product_name: str
    supplier_product_code: str
    cost: Decimal
    minimum_order_quantity: int
    pack_size: int
    lead_time_days: int


class SupplierOut(BaseModel):
    id: UUID
    name: str
    email: str
    lead_time_days: int
    terms: list[SupplierTerm]


class InventoryOut(BaseModel):
    id: UUID
    product_id: UUID
    store_id: UUID
    product_name: str
    sku: str
    store_name: str
    on_hand: int
    reserved: int
    available: int
    reorder_point: int
    safety_stock: int
    unit_cost: Decimal


class Adjustment(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    delta: int = Field(ge=-1000000, le=1000000, strict=True)
    reason: str = Field(min_length=5, max_length=80)

    @model_validator(mode="after")
    def nonzero(self):
        if self.delta == 0:
            raise ValueError("Adjustment must change stock")
        if not self.reason.strip():
            raise ValueError("A reason is required")
        return self


class MovementOut(BaseModel):
    id: UUID
    delta: int
    reason: str
    created_at: datetime
    actor_name: str


class OrderItemIn(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    product_id: UUID
    quantity: int = Field(gt=0, le=1000000, strict=True)


class OrderCreate(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    store_id: UUID
    supplier_id: UUID
    items: list[OrderItemIn] = Field(min_length=1, max_length=50)

    @model_validator(mode="after")
    def unique_products(self):
        if len({item.product_id for item in self.items}) != len(self.items):
            raise ValueError("Each product can occur only once")
        return self


class OrderDecision(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    reason: str = Field(default="", max_length=500)


class OrderItemOut(BaseModel):
    product_id: UUID
    product_name: str
    quantity: int
    unit_cost: Decimal
    line_total: Decimal


class ApprovalOut(BaseModel):
    id: UUID
    decision: str
    reason: str | None
    actor_name: str
    created_at: datetime


class OrderOut(BaseModel):
    id: UUID
    store_id: UUID
    store_name: str
    supplier_id: UUID
    supplier_name: str
    status: Literal["draft", "pending", "approved", "rejected", "received"]
    total: Decimal
    created_at: datetime
    items: list[OrderItemOut]
    approvals: list[ApprovalOut]


class SaleOut(BaseModel):
    id: UUID
    store_name: str
    sold_at: datetime
    total: Decimal
    gross_profit: Decimal
    item_count: int


class TrendPoint(BaseModel):
    date: date
    revenue: Decimal
    gross_profit: Decimal
    order_count: int


class StoreRevenue(BaseModel):
    name: str
    revenue: Decimal
    order_count: int


class CategoryRevenue(BaseModel):
    name: str
    revenue: Decimal


class ProductPerformance(BaseModel):
    id: UUID
    name: str
    sku: str
    quantity: int
    revenue: Decimal


class ActivityOut(BaseModel):
    id: UUID
    action: str
    created_at: datetime
    actor_name: str


class DashboardOut(BaseModel):
    currency: Literal["INR"] = "INR"
    revenue: Decimal
    gross_profit: Decimal
    gross_margin: Decimal
    order_count: int
    average_order_value: Decimal
    revenue_change_percent: Decimal | None
    low_stock_count: int
    out_of_stock_count: int
    inventory_valuation: Decimal
    pending_purchase_orders: int
    trend: list[TrendPoint]
    by_store: list[StoreRevenue]
    by_category: list[CategoryRevenue]
    top_products: list[ProductPerformance]
    slow_products: list[ProductPerformance]
    recent_activity: list[ActivityOut]
