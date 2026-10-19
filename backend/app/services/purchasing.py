"""Explicit human purchase approval and transactional stock updates."""

from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import (
    AuditLog,
    InventoryBalance,
    InventoryMovement,
    Product,
    ProductSupplier,
    PurchaseOrder,
    PurchaseOrderApproval,
    PurchaseOrderItem,
    Store,
    Supplier,
    User,
)
from app.schemas.retail import Adjustment, OrderCreate
from app.services.retail import ZERO, ensure_manager, inventory_detail, money


async def lock_idempotency(session: AsyncSession, key: str):
    # Serialize matching retries before checking uniqueness; no unrestricted SQL tool exists.
    await session.execute(select(func.pg_advisory_xact_lock(func.hashtextextended(key, 0))))


async def adjust_stock(
    session: AsyncSession, balance_id: UUID, payload: Adjustment, actor: User, key: str
):
    ensure_manager(actor)
    await lock_idempotency(session, key)
    prior = await session.scalar(
        select(InventoryMovement).where(InventoryMovement.idempotency_key == key)
    )
    balance = await session.scalar(
        select(InventoryBalance)
        .where(
            InventoryBalance.id == balance_id,
        )
        .with_for_update()
    )
    if balance is None:
        raise HTTPException(404, "Inventory balance not found")
    if prior:
        audit = await session.get(AuditLog, prior.audit_id)
        if (
            prior.store_id != balance.store_id
            or prior.product_id != balance.product_id
            or prior.quantity_delta != payload.delta
            or prior.reason != payload.reason
            or audit.actor_id != actor.id
        ):
            raise HTTPException(409, "Idempotency key was already used for another request")
        return await inventory_detail(session, balance_id)
    next_quantity = balance.quantity + payload.delta
    if next_quantity > 2_147_483_647:
        raise HTTPException(409, "Stock exceeds the supported quantity")
    if next_quantity < balance.reserved:
        raise HTTPException(409, "Adjustment would reduce stock below reserved quantity")
    audit = AuditLog(
        actor_id=actor.id,
        action="inventory.adjusted",
        entity_type="inventory",
        entity_id=balance.id,
        details={"before": balance.quantity, "after": next_quantity, "reason": payload.reason},
    )
    session.add(audit)
    await session.flush()
    session.add(
        InventoryMovement(
            store_id=balance.store_id,
            product_id=balance.product_id,
            quantity_delta=payload.delta,
            reason=payload.reason,
            audit_id=audit.id,
            actor_id=actor.id,
            idempotency_key=key,
        )
    )
    balance.quantity = next_quantity
    await session.commit()
    return await inventory_detail(session, balance_id)


async def order_output(session: AsyncSession, order_id: UUID):
    row = (
        (
            await session.execute(
                select(
                    PurchaseOrder.id,
                    PurchaseOrder.store_id,
                    Store.name.label("store_name"),
                    PurchaseOrder.supplier_id,
                    Supplier.name.label("supplier_name"),
                    PurchaseOrder.status,
                    PurchaseOrder.total,
                    PurchaseOrder.created_at,
                )
                .join(Store, PurchaseOrder.store_id == Store.id)
                .join(
                    Supplier,
                    PurchaseOrder.supplier_id == Supplier.id,
                )
                .where(PurchaseOrder.id == order_id)
            )
        )
        .mappings()
        .one_or_none()
    )
    if row is None:
        raise HTTPException(404, "Purchase order not found")
    items = (
        (
            await session.execute(
                select(
                    PurchaseOrderItem.product_id,
                    Product.name.label("product_name"),
                    PurchaseOrderItem.quantity,
                    PurchaseOrderItem.unit_cost,
                    (PurchaseOrderItem.quantity * PurchaseOrderItem.unit_cost).label("line_total"),
                )
                .join(Product, Product.id == PurchaseOrderItem.product_id)
                .where(
                    PurchaseOrderItem.purchase_order_id == order_id,
                )
                .order_by(Product.name)
            )
        )
        .mappings()
        .all()
    )
    approvals = (
        (
            await session.execute(
                select(
                    PurchaseOrderApproval.id,
                    PurchaseOrderApproval.decision,
                    PurchaseOrderApproval.note.label("reason"),
                    User.name.label("actor_name"),
                    PurchaseOrderApproval.created_at,
                )
                .join(User, User.id == PurchaseOrderApproval.actor_id)
                .where(
                    PurchaseOrderApproval.purchase_order_id == order_id,
                )
                .order_by(PurchaseOrderApproval.created_at)
            )
        )
        .mappings()
        .all()
    )
    return {
        **dict(row),
        "items": [dict(item) for item in items],
        "approvals": [dict(item) for item in approvals],
    }


async def create_order(session: AsyncSession, payload: OrderCreate, actor: User, key: str):
    ensure_manager(actor)
    await lock_idempotency(session, key)
    prior = await session.scalar(select(PurchaseOrder).where(PurchaseOrder.idempotency_key == key))
    if prior:
        previous_items = (
            await session.execute(
                select(
                    PurchaseOrderItem.product_id,
                    PurchaseOrderItem.quantity,
                ).where(PurchaseOrderItem.purchase_order_id == prior.id)
            )
        ).all()
        expected = {(item.product_id, item.quantity) for item in payload.items}
        if (
            prior.store_id != payload.store_id
            or prior.supplier_id != payload.supplier_id
            or prior.created_by != actor.id
            or set(previous_items) != expected
        ):
            raise HTTPException(409, "Idempotency key was already used for another request")
        return await order_output(session, prior.id)
    if not await session.get(Store, payload.store_id):
        raise HTTPException(404, "Store not found")
    if not await session.get(Supplier, payload.supplier_id):
        raise HTTPException(404, "Supplier not found")
    terms = (
        await session.scalars(
            select(ProductSupplier)
            .join(
                Product,
                Product.id == ProductSupplier.product_id,
            )
            .where(ProductSupplier.supplier_id == payload.supplier_id, Product.active.is_(True))
        )
    ).all()
    by_product = {term.product_id: term for term in terms}
    total = ZERO
    for item in payload.items:
        term = by_product.get(item.product_id)
        if term is None:
            raise HTTPException(422, "A selected product is not supplied by this supplier")
        if item.quantity < term.minimum_order_quantity or item.quantity % term.pack_size != 0:
            raise HTTPException(422, "Quantity must satisfy supplier minimum and pack size")
        total += term.unit_cost * item.quantity
    if total > 9999999999:
        raise HTTPException(422, "Purchase order exceeds the supported total")
    order = PurchaseOrder(
        store_id=payload.store_id,
        supplier_id=payload.supplier_id,
        created_by=actor.id,
        status="draft",
        total=money(total),
        idempotency_key=key,
    )
    session.add(order)
    await session.flush()
    for item in payload.items:
        session.add(
            PurchaseOrderItem(
                purchase_order_id=order.id,
                product_id=item.product_id,
                quantity=item.quantity,
                unit_cost=by_product[item.product_id].unit_cost,
            )
        )
    session.add(
        AuditLog(
            actor_id=actor.id,
            action="purchase_order.created",
            entity_type="purchase_order",
            entity_id=order.id,
            details={"total": str(order.total)},
        )
    )
    await session.commit()
    return await order_output(session, order.id)


TRANSITIONS = {
    "submit": ("draft", "pending"),
    "approve": ("pending", "approved"),
    "reject": ("pending", "rejected"),
    "receive": ("approved", "received"),
}


async def transition_order(
    session: AsyncSession, order_id: UUID, action: str, actor: User, key: str, reason: str
):
    if action not in TRANSITIONS:
        raise HTTPException(404, "Unknown purchase order action")
    if action == "reject" and len(reason.strip()) < 5:
        raise HTTPException(422, "Rejection requires a reason of at least five characters")
    ensure_manager(actor)
    await lock_idempotency(session, key)
    prior = await session.scalar(select(AuditLog).where(AuditLog.idempotency_key == key))
    if prior:
        if (
            prior.actor_id != actor.id
            or prior.entity_id != order_id
            or prior.action != f"purchase_order.{action}"
            or prior.details.get("reason") != reason
        ):
            raise HTTPException(409, "Idempotency key was already used for another request")
        return await order_output(session, order_id)
    order = await session.scalar(
        select(PurchaseOrder).where(PurchaseOrder.id == order_id).with_for_update()
    )
    if not order:
        raise HTTPException(404, "Purchase order not found")
    source, destination = TRANSITIONS[action]
    if order.status != source:
        raise HTTPException(409, f"Action requires {source} status; order is {order.status}")
    audit = AuditLog(
        actor_id=actor.id,
        action=f"purchase_order.{action}",
        entity_type="purchase_order",
        entity_id=order_id,
        idempotency_key=key,
        details={"from": source, "to": destination, "reason": reason},
    )
    session.add(audit)
    await session.flush()
    if action in ("approve", "reject"):
        session.add(
            PurchaseOrderApproval(
                purchase_order_id=order_id,
                actor_id=actor.id,
                idempotency_key=key,
                decision=destination,
                note=reason,
            )
        )
    if action == "receive":
        items = (
            await session.scalars(
                select(PurchaseOrderItem)
                .where(
                    PurchaseOrderItem.purchase_order_id == order_id,
                )
                .order_by(PurchaseOrderItem.product_id)
            )
        ).all()
        for item in items:
            await session.execute(
                insert(InventoryBalance)
                .values(
                    store_id=order.store_id,
                    product_id=item.product_id,
                    quantity=0,
                    reserved=0,
                    safety_stock=5,
                )
                .on_conflict_do_nothing(
                    index_elements=[InventoryBalance.store_id, InventoryBalance.product_id]
                )
            )
            balance = await session.scalar(
                select(InventoryBalance)
                .where(
                    InventoryBalance.store_id == order.store_id,
                    InventoryBalance.product_id == item.product_id,
                )
                .with_for_update()
            )
            if balance.quantity + item.quantity > 2_147_483_647:
                raise HTTPException(409, "Stock exceeds the supported quantity")
            balance.quantity += item.quantity
            session.add(
                InventoryMovement(
                    store_id=order.store_id,
                    product_id=item.product_id,
                    quantity_delta=item.quantity,
                    reason="Purchase order received internally",
                    audit_id=audit.id,
                    actor_id=actor.id,
                    idempotency_key=f"receive:{order.id}:{item.product_id}",
                )
            )
    order.status = destination
    await session.commit()
    return await order_output(session, order_id)
