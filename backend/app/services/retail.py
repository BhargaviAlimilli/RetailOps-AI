"""Retail reporting and auditable mutation services."""

from datetime import UTC, date, datetime, time, timedelta
from decimal import Decimal
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import (
    AuditLog,
    Category,
    InventoryBalance,
    Product,
    ProductSupplier,
    PurchaseOrder,
    Store,
    Supplier,
    User,
)
from app.repositories.retail import inventory_statement, products_statement, sale_evidence_statement
from app.schemas.retail import ProductCreate

ZERO = Decimal("0.00")
CENT = Decimal("0.01")


def ensure_manager(actor: User) -> None:
    if actor.role not in {"admin", "manager"}:
        raise HTTPException(403, "Manager role required")


def money(value) -> Decimal:
    return Decimal(value or 0).quantize(CENT)


def reporting_period(start_date: date | None, end_date: date | None):
    end_date = end_date or datetime.now(UTC).date()
    start_date = start_date or end_date - timedelta(days=27)
    if not (1900 <= start_date.year <= 2100 and 1900 <= end_date.year <= 2100):
        raise HTTPException(422, "Reporting dates must be between 1900 and 2100")
    days = (end_date - start_date).days + 1
    if not 1 <= days <= 366:
        raise HTTPException(422, "Choose an ordered date range of at most 366 days")
    return (
        datetime.combine(start_date, time.min, UTC),
        datetime.combine(
            end_date + timedelta(days=1),
            time.min,
            UTC,
        ),
        days,
    )


async def product_detail(session: AsyncSession, product_id: UUID):
    row = (
        (await session.execute(products_statement().where(Product.id == product_id)))
        .mappings()
        .one_or_none()
    )
    if row is None:
        raise HTTPException(404, "Product not found")
    return dict(row)


async def inventory_detail(session: AsyncSession, balance_id: UUID):
    row = (
        (await session.execute(inventory_statement().where(InventoryBalance.id == balance_id)))
        .mappings()
        .one_or_none()
    )
    if row is None:
        raise HTTPException(404, "Inventory balance not found")
    return dict(row)


async def create_product(session: AsyncSession, payload: ProductCreate, actor: User):
    ensure_manager(actor)
    if not await session.get(Category, payload.category_id):
        raise HTTPException(404, "Category not found")
    if await session.scalar(select(Product.id).where(Product.sku == payload.sku)):
        raise HTTPException(409, "SKU already exists")
    product = Product(
        sku=payload.sku,
        name=payload.name.strip(),
        category_id=payload.category_id,
        cost=payload.unit_cost,
        price=payload.unit_price,
        reorder_point=payload.reorder_point,
    )
    session.add(product)
    try:
        await session.flush()
    except IntegrityError as error:
        await session.rollback()
        raise HTTPException(409, "Product conflicts with an existing catalog record") from error
    for store_id in (await session.scalars(select(Store.id))).all():
        session.add(
            InventoryBalance(
                store_id=store_id, product_id=product.id, quantity=0, reserved=0, safety_stock=5
            )
        )
    session.add(
        AuditLog(
            actor_id=actor.id,
            action="product.created",
            entity_type="product",
            entity_id=product.id,
            details={"sku": product.sku},
        )
    )
    await session.commit()
    return await product_detail(session, product.id)


async def suppliers(session: AsyncSession):
    rows = (await session.scalars(select(Supplier).order_by(Supplier.name))).all()
    terms = (
        (
            await session.execute(
                select(
                    ProductSupplier.supplier_id,
                    ProductSupplier.product_id,
                    Product.name.label("product_name"),
                    ProductSupplier.supplier_product_code,
                    ProductSupplier.unit_cost.label("cost"),
                    ProductSupplier.minimum_order_quantity,
                    ProductSupplier.pack_size,
                    ProductSupplier.lead_time_days,
                )
                .join(Product, ProductSupplier.product_id == Product.id)
                .order_by(Product.name)
            )
        )
        .mappings()
        .all()
    )
    grouped: dict[UUID, list[dict]] = {}
    for term in terms:
        item = dict(term)
        supplier_id = item.pop("supplier_id")
        grouped.setdefault(supplier_id, []).append(item)
    return [
        {
            "id": supplier.id,
            "name": supplier.name,
            "email": supplier.email,
            "lead_time_days": supplier.lead_time_days,
            "terms": grouped.get(supplier.id, []),
        }
        for supplier in rows
    ]


async def dashboard(
    session: AsyncSession, start_date=None, end_date=None, store_id=None, category_id=None
):
    start, end, days = reporting_period(start_date, end_date)
    evidence = sale_evidence_statement(start, end, store_id, category_id).subquery()
    previous = sale_evidence_statement(
        start - timedelta(days=days), start, store_id, category_id
    ).subquery()
    totals = (
        (
            await session.execute(
                select(
                    func.coalesce(func.sum(evidence.c.revenue), 0).label("revenue"),
                    func.coalesce(func.sum(evidence.c.gross_profit), 0).label("gross_profit"),
                    func.count(func.distinct(evidence.c.sale_id)).label("orders"),
                )
            )
        )
        .mappings()
        .one()
    )
    revenue = money(totals["revenue"])
    profit = money(totals["gross_profit"])
    orders = totals["orders"]
    previous_revenue = money(await session.scalar(select(func.sum(previous.c.revenue))))
    utc_day = func.date(func.timezone("UTC", evidence.c.sold_at))
    trend_rows = (
        (
            await session.execute(
                select(
                    utc_day.label("date"),
                    func.sum(evidence.c.revenue).label("revenue"),
                    func.sum(evidence.c.gross_profit).label("gross_profit"),
                    func.count(func.distinct(evidence.c.sale_id)).label("order_count"),
                ).group_by(utc_day)
            )
        )
        .mappings()
        .all()
    )
    points = {row["date"]: dict(row) for row in trend_rows}
    trend = []
    for offset in range(days):
        day = (start + timedelta(days=offset)).date()
        trend.append(
            points.get(day, {"date": day, "revenue": ZERO, "gross_profit": ZERO, "order_count": 0})
        )
    by_store = (
        (
            await session.execute(
                select(
                    evidence.c.store_name.label("name"),
                    func.sum(evidence.c.revenue).label("revenue"),
                    func.count(func.distinct(evidence.c.sale_id)).label("order_count"),
                )
                .group_by(evidence.c.store_id, evidence.c.store_name)
                .order_by(func.sum(evidence.c.revenue).desc())
            )
        )
        .mappings()
        .all()
    )
    by_category = (
        (
            await session.execute(
                select(
                    evidence.c.category_name.label("name"),
                    func.sum(evidence.c.revenue).label("revenue"),
                )
                .group_by(evidence.c.category_name)
                .order_by(func.sum(evidence.c.revenue).desc())
            )
        )
        .mappings()
        .all()
    )
    performance = select(
        evidence.c.product_id.label("id"),
        evidence.c.product_name.label("name"),
        evidence.c.sku,
        func.sum(evidence.c.quantity).label("quantity"),
        func.sum(evidence.c.revenue).label("revenue"),
    ).group_by(evidence.c.product_id, evidence.c.product_name, evidence.c.sku)
    top = (
        (
            await session.execute(
                performance.order_by(
                    func.sum(evidence.c.revenue).desc(), evidence.c.product_id
                ).limit(5)
            )
        )
        .mappings()
        .all()
    )
    # Include zero-sale products; slow-moving must not silently exclude unsold stock.
    quantities = (
        select(
            evidence.c.product_id,
            func.sum(evidence.c.quantity).label("quantity"),
            func.sum(evidence.c.revenue).label("revenue"),
        )
        .group_by(evidence.c.product_id)
        .subquery()
    )
    slow_statement = (
        select(
            Product.id,
            Product.name,
            Product.sku,
            func.coalesce(quantities.c.quantity, 0).label("quantity"),
            func.coalesce(quantities.c.revenue, 0).label("revenue"),
        )
        .outerjoin(quantities, quantities.c.product_id == Product.id)
        .where(Product.active.is_(True))
    )
    if category_id:
        slow_statement = slow_statement.where(Product.category_id == category_id)
    if store_id:
        slow_statement = slow_statement.where(
            select(InventoryBalance.id)
            .where(
                InventoryBalance.product_id == Product.id,
                InventoryBalance.store_id == store_id,
            )
            .exists()
        )
    slow = (
        (
            await session.execute(
                slow_statement.order_by(
                    func.coalesce(quantities.c.quantity, 0),
                    Product.id,
                ).limit(5)
            )
        )
        .mappings()
        .all()
    )
    stock = inventory_statement()
    if store_id:
        stock = stock.where(InventoryBalance.store_id == store_id)
    if category_id:
        stock = stock.where(Product.category_id == category_id)
    stock_data = stock.subquery()
    inventory = (
        (
            await session.execute(
                select(
                    func.count()
                    .filter(
                        (stock_data.c.available > 0)
                        & (stock_data.c.available <= stock_data.c.reorder_point)
                    )
                    .label("low"),
                    func.count().filter(stock_data.c.available <= 0).label("out"),
                    func.coalesce(func.sum(stock_data.c.on_hand * stock_data.c.unit_cost), 0).label(
                        "valuation"
                    ),
                )
            )
        )
        .mappings()
        .one()
    )
    pending_statement = (
        select(func.count()).select_from(PurchaseOrder).where(PurchaseOrder.status == "pending")
    )
    if store_id:
        pending_statement = pending_statement.where(PurchaseOrder.store_id == store_id)
    if category_id:
        from app.db.models import PurchaseOrderItem

        pending_statement = pending_statement.where(
            select(PurchaseOrderItem.id)
            .join(
                Product,
                Product.id == PurchaseOrderItem.product_id,
            )
            .where(
                PurchaseOrderItem.purchase_order_id == PurchaseOrder.id,
                Product.category_id == category_id,
            )
            .exists()
        )
    pending = await session.scalar(pending_statement)
    activity_statement = select(
        AuditLog.id,
        AuditLog.action,
        AuditLog.created_at,
        func.coalesce(User.name, "System").label("actor_name"),
    ).outerjoin(User, AuditLog.actor_id == User.id)
    # Activity is organization-wide; label separately from period-specific sales metrics.
    activity = (
        (await session.execute(activity_statement.order_by(AuditLog.created_at.desc()).limit(8)))
        .mappings()
        .all()
    )
    return {
        "currency": "INR",
        "revenue": revenue,
        "gross_profit": profit,
        "gross_margin": money(profit / revenue * 100) if revenue else ZERO,
        "order_count": orders,
        "average_order_value": money(revenue / orders) if orders else ZERO,
        "revenue_change_percent": money((revenue - previous_revenue) / previous_revenue * 100)
        if previous_revenue
        else None,
        "low_stock_count": inventory["low"],
        "out_of_stock_count": inventory["out"],
        "inventory_valuation": money(inventory["valuation"]),
        "pending_purchase_orders": pending or 0,
        "trend": trend,
        "by_store": [dict(row) for row in by_store],
        "by_category": [dict(row) for row in by_category],
        "top_products": [dict(row) for row in top],
        "slow_products": [dict(row) for row in slow],
        "recent_activity": [dict(row) for row in activity],
    }
