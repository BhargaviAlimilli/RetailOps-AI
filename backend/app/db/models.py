"""Relational source of truth for the synthetic retail workspace."""

import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    Uuid,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class Identity:
    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class User(Identity, Base):
    __tablename__ = "users"
    email: Mapped[str] = mapped_column(String(254), unique=True)
    name: Mapped[str] = mapped_column(String(120))
    role: Mapped[str] = mapped_column(String(20))
    password_hash: Mapped[str] = mapped_column(String(256))
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    __table_args__ = (CheckConstraint("role IN ('admin','manager','analyst')", name="user_role"),)


class Session(Identity, Base):
    __tablename__ = "sessions"
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), index=True)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class Store(Identity, Base):
    __tablename__ = "stores"
    code: Mapped[str] = mapped_column(String(30), unique=True)
    name: Mapped[str] = mapped_column(String(120))


class Category(Identity, Base):
    __tablename__ = "categories"
    name: Mapped[str] = mapped_column(String(100), unique=True)


class Product(Identity, Base):
    __tablename__ = "products"
    sku: Mapped[str] = mapped_column(String(50), unique=True)
    name: Mapped[str] = mapped_column(String(160))
    category_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("categories.id"), index=True)
    price: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    cost: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    reorder_point: Mapped[int] = mapped_column(Integer, default=10)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    __table_args__ = (
        CheckConstraint("price >= 0 AND cost >= 0 AND reorder_point >= 0", name="product_values"),
    )


class Supplier(Identity, Base):
    __tablename__ = "suppliers"
    name: Mapped[str] = mapped_column(String(120), unique=True)
    email: Mapped[str] = mapped_column(String(254))
    lead_time_days: Mapped[int] = mapped_column(Integer)
    __table_args__ = (CheckConstraint("lead_time_days >= 0", name="supplier_lead_time"),)


class ProductSupplier(Identity, Base):
    __tablename__ = "product_suppliers"
    product_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("products.id"), index=True)
    supplier_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("suppliers.id"), index=True)
    unit_cost: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    supplier_product_code: Mapped[str] = mapped_column(String(80))
    minimum_order_quantity: Mapped[int] = mapped_column(Integer, default=1)
    pack_size: Mapped[int] = mapped_column(Integer, default=1)
    lead_time_days: Mapped[int] = mapped_column(Integer, default=3)
    __table_args__ = (
        UniqueConstraint("product_id", "supplier_id"),
        CheckConstraint(
            "unit_cost >= 0 AND minimum_order_quantity > 0 "
            "AND pack_size > 0 AND lead_time_days >= 0",
            name="supplier_cost",
        ),
    )


class InventoryBalance(Identity, Base):
    __tablename__ = "inventory_balances"
    store_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("stores.id"), index=True)
    product_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("products.id"), index=True)
    quantity: Mapped[int] = mapped_column(Integer)
    reserved: Mapped[int] = mapped_column(Integer, default=0)
    safety_stock: Mapped[int] = mapped_column(Integer, default=5)
    __table_args__ = (
        UniqueConstraint("store_id", "product_id"),
        CheckConstraint(
            "quantity >= 0 AND reserved >= 0 AND reserved <= quantity AND safety_stock >= 0",
            name="inventory_nonnegative",
        ),
    )


class AuditLog(Identity, Base):
    __tablename__ = "audit_logs"
    actor_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"), index=True)
    action: Mapped[str] = mapped_column(String(80), index=True)
    entity_type: Mapped[str] = mapped_column(String(60))
    entity_id: Mapped[uuid.UUID | None] = mapped_column(Uuid)
    details: Mapped[dict] = mapped_column(JSONB, default=dict)
    idempotency_key: Mapped[str | None] = mapped_column(String(128), unique=True)


class InventoryMovement(Identity, Base):
    __tablename__ = "inventory_movements"
    store_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("stores.id"), index=True)
    product_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("products.id"), index=True)
    quantity_delta: Mapped[int] = mapped_column(Integer)
    reason: Mapped[str] = mapped_column(String(80))
    audit_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("audit_logs.id"))
    actor_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))
    idempotency_key: Mapped[str] = mapped_column(String(128), unique=True)
    __table_args__ = (CheckConstraint("quantity_delta <> 0", name="movement_nonzero"),)


class Sale(Identity, Base):
    __tablename__ = "sales"
    store_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("stores.id"), index=True)
    sold_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    total: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    __table_args__ = (CheckConstraint("total >= 0", name="sale_total"),)


class SaleItem(Identity, Base):
    __tablename__ = "sale_items"
    sale_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("sales.id"), index=True)
    product_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("products.id"), index=True)
    quantity: Mapped[int] = mapped_column(Integer)
    unit_price: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    unit_cost: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    __table_args__ = (
        CheckConstraint(
            "quantity > 0 AND unit_price >= 0 AND unit_cost >= 0", name="sale_item_values"
        ),
    )


class PurchaseOrder(Identity, Base):
    __tablename__ = "purchase_orders"
    store_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("stores.id"), index=True)
    supplier_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("suppliers.id"), index=True)
    created_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))
    status: Mapped[str] = mapped_column(String(20), default="draft", index=True)
    total: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    idempotency_key: Mapped[str] = mapped_column(String(128), unique=True)
    __table_args__ = (
        CheckConstraint(
            "status IN ('draft','pending','approved','rejected','received')",
            name="purchase_order_status",
        ),
        CheckConstraint("total >= 0", name="purchase_order_total"),
    )


class PurchaseOrderItem(Identity, Base):
    __tablename__ = "purchase_order_items"
    purchase_order_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("purchase_orders.id"), index=True
    )
    product_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("products.id"), index=True)
    quantity: Mapped[int] = mapped_column(Integer)
    unit_cost: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    __table_args__ = (
        UniqueConstraint("purchase_order_id", "product_id"),
        CheckConstraint("quantity > 0 AND unit_cost >= 0", name="purchase_item_values"),
    )


class PurchaseOrderApproval(Identity, Base):
    __tablename__ = "purchase_order_approvals"
    purchase_order_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("purchase_orders.id"), unique=True
    )
    actor_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))
    idempotency_key: Mapped[str] = mapped_column(String(128), unique=True)
    decision: Mapped[str] = mapped_column(String(20))
    note: Mapped[str | None] = mapped_column(Text)
    __table_args__ = (
        CheckConstraint("decision IN ('approved','rejected')", name="approval_decision"),
    )


Index("ix_audit_logs_created_at", AuditLog.created_at)


class Conversation(Identity, Base):
    __tablename__ = "conversations"
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), index=True)
    title: Mapped[str] = mapped_column(String(120))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    active_request_id: Mapped[uuid.UUID | None] = mapped_column(Uuid)
    lease_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class ConversationMessage(Identity, Base):
    __tablename__ = "conversation_messages"
    conversation_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("conversations.id"), index=True)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), index=True)
    request_id: Mapped[uuid.UUID] = mapped_column(Uuid)
    ordinal: Mapped[int] = mapped_column(Integer)
    role: Mapped[str] = mapped_column(String(20))
    content: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(String(20))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    usage: Mapped[dict | None] = mapped_column(JSONB)
    error_code: Mapped[str | None] = mapped_column(String(60))
    finish_reason: Mapped[str | None] = mapped_column(String(40))
    __table_args__ = (
        UniqueConstraint("user_id", "request_id", "role"),
        UniqueConstraint("conversation_id", "ordinal"),
        CheckConstraint("role IN ('user','assistant')", name="conversation_message_role"),
        CheckConstraint(
            "status IN ('pending','streaming','completed','cancelled','error')",
            name="conversation_message_status",
        ),
        CheckConstraint("length(content) <= 32768", name="conversation_message_length"),
    )
