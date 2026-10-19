"""Composable SQLAlchemy statements; business transactions live in services."""

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Category, InventoryBalance, Product, Sale, SaleItem, Store


def products_statement():
    return (
        select(
            Product.id,
            Product.sku,
            Product.name,
            Product.category_id,
            Category.name.label("category_name"),
            Product.cost.label("unit_cost"),
            Product.price.label("unit_price"),
        )
        .join(Category, Product.category_id == Category.id)
        .where(Product.active.is_(True))
    )


def inventory_statement():
    available = InventoryBalance.quantity - InventoryBalance.reserved
    return (
        select(
            InventoryBalance.id,
            InventoryBalance.product_id,
            InventoryBalance.store_id,
            Product.name.label("product_name"),
            Product.sku,
            Store.name.label("store_name"),
            InventoryBalance.quantity.label("on_hand"),
            InventoryBalance.reserved,
            available.label("available"),
            Product.reorder_point,
            InventoryBalance.safety_stock,
            Product.cost.label("unit_cost"),
        )
        .join(Product, InventoryBalance.product_id == Product.id)
        .join(
            Store,
            InventoryBalance.store_id == Store.id,
        )
        .where(Product.active.is_(True))
    )


def sale_evidence_statement(start, end, store_id=None, category_id=None):
    statement = (
        select(
            Sale.id.label("sale_id"),
            Sale.sold_at,
            Sale.store_id,
            Store.name.label("store_name"),
            Product.id.label("product_id"),
            Product.name.label("product_name"),
            Product.sku,
            Category.name.label("category_name"),
            SaleItem.quantity,
            (SaleItem.quantity * SaleItem.unit_price).label("revenue"),
            (SaleItem.quantity * (SaleItem.unit_price - SaleItem.unit_cost)).label("gross_profit"),
        )
        .select_from(SaleItem)
        .join(Sale, SaleItem.sale_id == Sale.id)
        .join(
            Product,
            SaleItem.product_id == Product.id,
        )
        .join(Category, Product.category_id == Category.id)
        .join(Store, Sale.store_id == Store.id)
        .where(
            Sale.sold_at >= start,
            Sale.sold_at < end,
        )
    )
    if store_id:
        statement = statement.where(Sale.store_id == store_id)
    if category_id:
        statement = statement.where(Product.category_id == category_id)
    return statement


async def paginate(session: AsyncSession, statement, page: int, page_size: int, ordering):
    total = await session.scalar(select(func.count()).select_from(statement.subquery()))
    rows = (
        (
            await session.execute(
                statement.order_by(*ordering).offset((page - 1) * page_size).limit(page_size)
            )
        )
        .mappings()
        .all()
    )
    return {
        "items": [dict(row) for row in rows],
        "total": total or 0,
        "page": page,
        "page_size": page_size,
    }
