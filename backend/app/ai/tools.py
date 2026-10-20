"""Allowlisted, validated retail tools. Models cannot supply SQL or approve actions."""

import json
from datetime import UTC, date, datetime, timedelta
from decimal import ROUND_CEILING, Decimal
from uuid import UUID

from fastapi import HTTPException
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.provider import ToolDefinition
from app.core.config import Settings
from app.db.models import (
    InventoryBalance,
    Product,
    ProductSupplier,
    PurchaseOrder,
    PurchaseOrderItem,
    Sale,
    SaleItem,
    Store,
    Supplier,
)
from app.repositories.retail import inventory_statement
from app.services import retail


class ToolInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    store_id: UUID | None = None


class SalesInput(ToolInput):
    start_date: date | None = None
    end_date: date | None = None


class InventoryInput(ToolInput):
    product_id: UUID | None = None
    limit: int = Field(default=20, ge=1, le=50)


class SupplierInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    product_id: UUID


class SearchInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    query: str = Field(min_length=1, max_length=2000)
    limit: int = Field(default=5, ge=1, le=5)


class ReorderInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    store_id: UUID
    product_id: UUID
    supplier_id: UUID
    cover_days: int = Field(default=7, ge=1, le=30)


TOOL_SCHEMAS = {
    "get_sales_summary": (
        SalesInput,
        "Database sales totals and period comparisons for completed UTC days.",
    ),
    "get_sales_trends": (
        SalesInput,
        "Daily revenue and gross profit; stockouts are correlation, not proven causation.",
    ),
    "get_top_products": (SalesInput, "Database top-selling and slow-moving products."),
    "get_inventory_levels": (
        InventoryInput,
        "Current inventory by store/product, including available and reserved stock.",
    ),
    "get_stockout_risks": (
        InventoryInput,
        "Current low/out-of-stock products; does not predict causation.",
    ),
    "get_supplier_for_product": (
        SupplierInput,
        "Authoritative supplier costs, lead times, minimums and pack sizes.",
    ),
    "search_documents": (
        SearchInput,
        "Search only the signed-in user's documents, returning persisted citations.",
    ),
    "calculate_reorder_quantity": (
        ReorderInput,
        "Recommend quantity from observed demand, lead time, stock and open orders; no mutation.",
    ),
}


def definitions() -> list[ToolDefinition]:
    return [
        ToolDefinition(name=name, description=description, parameters=schema.model_json_schema())
        for name, (schema, description) in TOOL_SCHEMAS.items()
    ]


def json_safe(value):
    return json.loads(json.dumps(value, default=str))


async def reorder(session: AsyncSession, args: ReorderInput) -> dict:
    product = await session.get(Product, args.product_id)
    store = await session.get(Store, args.store_id)
    supplier = await session.get(Supplier, args.supplier_id)
    term = await session.scalar(
        select(ProductSupplier).where(
            ProductSupplier.product_id == args.product_id,
            ProductSupplier.supplier_id == args.supplier_id,
        )
    )
    balance = await session.scalar(
        select(InventoryBalance).where(
            InventoryBalance.store_id == args.store_id,
            InventoryBalance.product_id == args.product_id,
        )
    )
    if not product or not product.active or not store or not supplier or not term or not balance:
        raise HTTPException(422, "Choose an active product, store balance and associated supplier")
    end = datetime.combine(datetime.now(UTC).date(), datetime.min.time(), UTC)
    start = end - timedelta(days=28)
    units = await session.scalar(
        select(func.coalesce(func.sum(SaleItem.quantity), 0))
        .join(
            Sale,
            Sale.id == SaleItem.sale_id,
        )
        .where(
            Sale.store_id == args.store_id,
            SaleItem.product_id == args.product_id,
            Sale.sold_at >= start,
            Sale.sold_at < end,
        )
    )
    inbound = await session.scalar(
        select(func.coalesce(func.sum(PurchaseOrderItem.quantity), 0))
        .join(
            PurchaseOrder,
            PurchaseOrder.id == PurchaseOrderItem.purchase_order_id,
        )
        .where(
            PurchaseOrder.store_id == args.store_id,
            PurchaseOrderItem.product_id == args.product_id,
            PurchaseOrder.status.in_(["pending", "approved"]),
        )
    )
    daily = Decimal(units) / Decimal(28)
    available = balance.quantity - balance.reserved
    target = max(
        product.reorder_point,
        balance.safety_stock
        + int(
            (daily * (term.lead_time_days + args.cover_days)).to_integral_value(
                rounding=ROUND_CEILING
            )
        ),
    )
    needed = max(0, target - available - int(inbound))
    quantity = 0 if needed == 0 else max(needed, term.minimum_order_quantity)
    quantity = ((quantity + term.pack_size - 1) // term.pack_size) * term.pack_size
    if quantity > 1_000_000:
        raise HTTPException(422, "Recommendation exceeds the supported order quantity")
    return json_safe(
        {
            "store_id": store.id,
            "store_name": store.name,
            "product_id": product.id,
            "product_name": product.name,
            "supplier_id": supplier.id,
            "supplier_name": supplier.name,
            "quantity": quantity,
            "unit_cost": term.unit_cost,
            "total": retail.money(term.unit_cost * quantity),
            "available": available,
            "open_order_quantity": int(inbound),
            "target": target,
            "daily_units_28_days": str(daily.quantize(Decimal("0.0001"))),
            "lead_time_days": term.lead_time_days,
            "pack_size": term.pack_size,
            "reason": "28 completed UTC days of sales; target covers supplier lead time plus "
            f"{args.cover_days} days and safety stock. Open pending/approved orders are deducted. "
            "Observed demand may understate lost sales during stockouts; this is a recommendation.",
        }
    )


async def execute(
    session: AsyncSession, user_id: UUID, name: str, arguments: dict, settings: Settings
) -> dict | list:
    if name not in TOOL_SCHEMAS:
        raise HTTPException(422, "Unknown or disallowed tool")
    args = TOOL_SCHEMAS[name][0].model_validate(arguments)
    if name.startswith("get_sales_") or name == "get_top_products":
        data = await retail.dashboard(session, args.start_date, args.end_date, args.store_id, None)
        start, exclusive_end, days = retail.reporting_period(args.start_date, args.end_date)
        period = {
            "start_date": start.date().isoformat(),
            "end_date": (exclusive_end.date() - timedelta(days=1)).isoformat(),
            "days": days,
            "timezone": "UTC",
        }
        if name == "get_sales_trends":
            return json_safe(
                {
                    "trend": data["trend"],
                    "period": period,
                    "interpretation": "Association does not establish causation.",
                }
            )
        if name == "get_top_products":
            return json_safe(
                {
                    "top_products": data["top_products"],
                    "slow_products": data["slow_products"],
                    "period": period,
                }
            )
        return json_safe(
            {
                "period": period,
                **{
                    key: data[key]
                    for key in (
                        "currency",
                        "revenue",
                        "gross_profit",
                        "order_count",
                        "revenue_change_percent",
                    )
                },
            }
        )
    if name in {"get_inventory_levels", "get_stockout_risks"}:
        statement = inventory_statement()
        if args.store_id:
            statement = statement.where(InventoryBalance.store_id == args.store_id)
        if args.product_id:
            statement = statement.where(InventoryBalance.product_id == args.product_id)
        if name == "get_stockout_risks":
            statement = statement.where(
                InventoryBalance.quantity - InventoryBalance.reserved <= Product.reorder_point
            )
        return json_safe(
            [
                dict(row)
                for row in (
                    await session.execute(
                        statement.order_by(Product.name, InventoryBalance.id).limit(args.limit)
                    )
                ).mappings()
            ]
        )
    if name == "get_supplier_for_product":
        rows = (
            await session.execute(
                select(
                    Supplier.id,
                    Supplier.name,
                    ProductSupplier.unit_cost,
                    ProductSupplier.minimum_order_quantity,
                    ProductSupplier.pack_size,
                    ProductSupplier.lead_time_days,
                )
                .join(ProductSupplier, ProductSupplier.supplier_id == Supplier.id)
                .where(ProductSupplier.product_id == args.product_id)
            )
        ).mappings()
        return json_safe([dict(row) for row in rows])
    if name == "search_documents":
        from app.rag.service import retrieve

        return {
            "citations": [
                citation.model_dump(mode="json")
                for citation in await retrieve(
                    session, user_id, args.query, args.limit, settings=settings
                )
            ]
        }
    if name == "calculate_reorder_quantity":
        return await reorder(session, args)
    raise HTTPException(422, "Tool unavailable")
