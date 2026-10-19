"""Authorized transactional stock and purchase workflows."""

from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, Header, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import current_user, get_session, require_manager
from app.db.models import AuditLog, InventoryMovement, PurchaseOrder, User
from app.repositories.retail import paginate
from app.schemas.retail import (
    Adjustment,
    InventoryOut,
    MovementOut,
    OrderCreate,
    OrderDecision,
    OrderOut,
    Page,
)
from app.services import purchasing
from app.services import retail as service

router = APIRouter(dependencies=[Depends(current_user)], tags=["purchasing and stock"])
Session = Annotated[AsyncSession, Depends(get_session)]
Manager = Annotated[User, Depends(require_manager)]
Key = Annotated[UUID, Header(alias="Idempotency-Key")]


@router.post("/inventory/{balance_id}/adjust", response_model=InventoryOut)
async def adjust_inventory(
    balance_id: UUID, payload: Adjustment, session: Session, actor: Manager, key: Key
):
    return await purchasing.adjust_stock(session, balance_id, payload, actor, str(key))


@router.get("/inventory/{balance_id}/movements", response_model=list[MovementOut])
async def movements(balance_id: UUID, session: Session):
    balance = await service.inventory_detail(session, balance_id)
    return (
        (
            await session.execute(
                select(
                    InventoryMovement.id,
                    InventoryMovement.quantity_delta.label("delta"),
                    InventoryMovement.reason,
                    InventoryMovement.created_at,
                    func.coalesce(User.name, "System").label("actor_name"),
                )
                .join(AuditLog, InventoryMovement.audit_id == AuditLog.id)
                .outerjoin(
                    User,
                    User.id == AuditLog.actor_id,
                )
                .where(
                    InventoryMovement.store_id == balance["store_id"],
                    InventoryMovement.product_id == balance["product_id"],
                )
                .order_by(
                    InventoryMovement.created_at.desc(),
                    InventoryMovement.id,
                )
                .limit(100)
            )
        )
        .mappings()
        .all()
    )


@router.get("/purchase-orders", response_model=Page[OrderOut])
async def orders(
    session: Session,
    status: Literal["all", "draft", "pending", "approved", "rejected", "received"] = "all",
    page: Annotated[int, Query(ge=1, le=100000)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
):
    statement = select(PurchaseOrder.id)
    if status != "all":
        statement = statement.where(PurchaseOrder.status == status)
    result = await paginate(
        session, statement, page, page_size, [PurchaseOrder.created_at.desc(), PurchaseOrder.id]
    )
    result["items"] = [
        await purchasing.order_output(session, item["id"]) for item in result["items"]
    ]
    return result


@router.post("/purchase-orders", response_model=OrderOut, status_code=201)
async def create_order(payload: OrderCreate, session: Session, actor: Manager, key: Key):
    return await purchasing.create_order(session, payload, actor, str(key))


@router.post("/purchase-orders/{order_id}/{action}", response_model=OrderOut)
async def transition(
    order_id: UUID,
    action: Literal["submit", "approve", "reject", "receive"],
    payload: OrderDecision,
    session: Session,
    actor: Manager,
    key: Key,
):
    return await purchasing.transition_order(
        session, order_id, action, actor, str(key), payload.reason
    )
