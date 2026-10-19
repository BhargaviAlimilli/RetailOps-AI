"""Authenticated retail endpoints; services enforce transactional business rules."""

from datetime import date
from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import current_user, get_session, require_manager
from app.db.models import (
    Category,
    InventoryBalance,
    Product,
    Store,
    User,
)
from app.repositories.retail import (
    inventory_statement,
    paginate,
    products_statement,
    sale_evidence_statement,
)
from app.schemas.retail import (
    CategoryOut,
    DashboardOut,
    InventoryOut,
    Page,
    ProductCreate,
    ProductOut,
    SaleOut,
    StoreOut,
    SupplierOut,
)
from app.services import retail as service

router = APIRouter(dependencies=[Depends(current_user)], tags=["retail"])
Session = Annotated[AsyncSession, Depends(get_session)]
Manager = Annotated[User, Depends(require_manager)]
PageNumber = Annotated[int, Query(ge=1, le=100000)]
PageSize = Annotated[int, Query(ge=1, le=100)]
Search = Annotated[str, Query(max_length=100)]


@router.get("/stores", response_model=list[StoreOut])
async def list_stores(session: Session):
    return (
        (await session.execute(select(Store.id, Store.name, Store.code).order_by(Store.name)))
        .mappings()
        .all()
    )


@router.get("/categories", response_model=list[CategoryOut])
async def list_categories(session: Session):
    return (
        (await session.execute(select(Category.id, Category.name).order_by(Category.name)))
        .mappings()
        .all()
    )


@router.get("/suppliers", response_model=list[SupplierOut])
async def list_suppliers(session: Session):
    return await service.suppliers(session)


@router.get("/products", response_model=Page[ProductOut])
async def list_products(
    session: Session,
    q: Search = "",
    category_id: UUID | None = None,
    page: PageNumber = 1,
    page_size: PageSize = 20,
):
    statement = products_statement()
    if q:
        # Autoescape ensures literal search text cannot become SQL wildcard operators.
        statement = statement.where(
            Product.name.icontains(q, autoescape=True) | Product.sku.icontains(q, autoescape=True)
        )
    if category_id:
        statement = statement.where(Product.category_id == category_id)
    return await paginate(session, statement, page, page_size, [Product.name, Product.id])


@router.get("/products/{product_id}", response_model=ProductOut)
async def get_product(product_id: UUID, session: Session):
    return await service.product_detail(session, product_id)


@router.post("/products", response_model=ProductOut, status_code=201)
async def add_product(payload: ProductCreate, session: Session, actor: Manager):
    return await service.create_product(session, payload, actor)


@router.get("/inventory", response_model=Page[InventoryOut])
async def list_inventory(
    session: Session,
    store_id: UUID | None = None,
    q: Search = "",
    status: Literal["all", "low", "out"] = "all",
    page: PageNumber = 1,
    page_size: PageSize = 20,
):
    statement = inventory_statement()
    if store_id:
        statement = statement.where(InventoryBalance.store_id == store_id)
    if q:
        statement = statement.where(
            Product.name.icontains(q, autoescape=True) | Product.sku.icontains(q, autoescape=True)
        )
    available = InventoryBalance.quantity - InventoryBalance.reserved
    if status == "low":
        statement = statement.where(available > 0, available <= Product.reorder_point)
    elif status == "out":
        statement = statement.where(available <= 0)
    return await paginate(
        session, statement, page, page_size, [Store.name, Product.name, InventoryBalance.id]
    )


@router.get("/dashboard", response_model=DashboardOut)
async def dashboard(
    session: Session,
    store_id: UUID | None = None,
    category_id: UUID | None = None,
    start_date: date | None = None,
    end_date: date | None = None,
):
    return await service.dashboard(session, start_date, end_date, store_id, category_id)


@router.get("/sales", response_model=Page[SaleOut])
async def sales(
    session: Session,
    store_id: UUID | None = None,
    start_date: date | None = None,
    end_date: date | None = None,
    page: PageNumber = 1,
    page_size: PageSize = 20,
):
    start, end, _ = service.reporting_period(start_date, end_date)
    evidence = sale_evidence_statement(start, end, store_id).subquery()
    statement = select(
        evidence.c.sale_id.label("id"),
        evidence.c.store_name,
        evidence.c.sold_at,
        func.sum(evidence.c.revenue).label("total"),
        func.sum(evidence.c.gross_profit).label("gross_profit"),
        func.sum(evidence.c.quantity).label("item_count"),
    ).group_by(evidence.c.sale_id, evidence.c.store_name, evidence.c.sold_at)
    return await paginate(
        session, statement, page, page_size, [evidence.c.sold_at.desc(), evidence.c.sale_id]
    )
