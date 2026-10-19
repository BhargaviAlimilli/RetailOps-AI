"""Populate only an empty local demo database with explicitly synthetic records."""

import asyncio
import os
import sys
import uuid
from datetime import UTC, datetime, timedelta
from decimal import Decimal

from sqlalchemy import func, select, text
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.core.config import Settings
from app.core.security import hash_password
from app.db.models import (
    AuditLog,
    Category,
    InventoryBalance,
    InventoryMovement,
    Product,
    ProductSupplier,
    PurchaseOrder,
    PurchaseOrderItem,
    Sale,
    SaleItem,
    Store,
    Supplier,
    User,
)

SEED_ACTION = "demo.seed.v1"


def validate_target(settings: Settings, password: str) -> str:
    if settings.environment != "development" or settings.database_url is None:
        raise ValueError("Demo seed requires development environment and explicit database URL")
    url = settings.database_url.get_secret_value()
    if make_url(url).database != "retailops_demo":
        raise ValueError("Demo seed is restricted to the retailops_demo database")
    if not 12 <= len(password) <= 256:
        raise ValueError("Set RETAILOPS_DEMO_PASSWORD with 12 to 256 characters")
    return url


async def seed_data(session, password: str) -> bool:
    """Single transaction. Never reset or overwrite any existing business data."""
    async with session.begin():
        await session.execute(text("SELECT pg_advisory_xact_lock(842718201)"))
        if await session.scalar(select(AuditLog.id).where(AuditLog.action == SEED_ACTION)):
            return False
        from app.db.models import Base

        for table in Base.metadata.sorted_tables:
            if await session.scalar(select(func.count()).select_from(table)):
                raise ValueError("Refusing to seed a nonempty unrecognized database")
        users = [
            User(
                id=uuid.uuid4(),
                email=f"{role}@retailops.demo",
                name=f"Demo {role.title()}",
                role=role,
                password_hash=hash_password(password),
            )
            for role in ("admin", "manager", "analyst")
        ]
        stores = [
            Store(id=uuid.uuid4(), code=code, name=name)
            for code, name in (
                ("HYD", "Hyderabad Central"),
                ("VJA", "Vijayawada Market"),
                ("VIZ", "Visakhapatnam Coast"),
            )
        ]
        categories = [
            Category(id=uuid.uuid4(), name=name) for name in ("Pantry", "Beverages", "Household")
        ]
        suppliers = [
            Supplier(
                id=uuid.uuid4(),
                name=name,
                email=f"supplier{i}@retailops.demo",
                lead_time_days=3 + i,
            )
            for i, name in enumerate(
                (
                    "Synthetic Harvest Supply",
                    "Synthetic Coastal Wholesale",
                    "Synthetic Daily Essentials",
                )
            )
        ]
        session.add_all([*users, *stores, *categories, *suppliers])
        await session.flush()
        names = (
            "Rice 5 kg",
            "Lentils 1 kg",
            "Sunflower Oil 1 L",
            "Flour 2 kg",
            "Tea 250 g",
            "Coffee 200 g",
            "Fruit Juice 1 L",
            "Water 1 L",
            "Dish Soap 500 ml",
            "Laundry Powder 1 kg",
            "Tissue Pack",
            "Floor Cleaner 1 L",
        )
        products = [
            Product(
                id=uuid.uuid4(),
                sku=f"DEMO-{i + 1:03}",
                name=name,
                category_id=categories[i // 4].id,
                price=Decimal(100 + i * 25),
                cost=Decimal(65 + i * 15),
                reorder_point=15,
            )
            for i, name in enumerate(names)
        ]
        session.add_all(products)
        await session.flush()
        for i, product in enumerate(products):
            session.add(
                ProductSupplier(
                    product_id=product.id,
                    supplier_id=suppliers[i // 4].id,
                    unit_cost=product.cost,
                    supplier_product_code=f"SYN-{i + 1:03}",
                    minimum_order_quantity=6,
                    pack_size=6,
                    lead_time_days=3 + i // 4,
                )
            )
        totals = {(store.id, product.id): 0 for store in stores for product in products}
        now = datetime.now(UTC).replace(hour=12, minute=0, second=0, microsecond=0)
        for days_ago in range(90, 0, -1):
            for store_index, store in enumerate(stores):
                sale = Sale(
                    id=uuid.uuid4(),
                    store_id=store.id,
                    sold_at=now - timedelta(days=days_ago),
                    total=Decimal(0),
                )
                session.add(sale)
                await session.flush()
                for i, product in enumerate(products):
                    # Deliberate recent decline at Hyderabad, still deterministic.
                    quantity = (1 if days_ago <= 14 and store_index == 0 else 3) + (i % 2)
                    totals[store.id, product.id] += quantity
                    sale.total += product.price * quantity
                    session.add(
                        SaleItem(
                            sale_id=sale.id,
                            product_id=product.id,
                            quantity=quantity,
                            unit_price=product.price,
                            unit_cost=product.cost,
                        )
                    )
        await session.flush()
        for store_index, store in enumerate(stores):
            for i, product in enumerate(products):
                ending = 0 if i == store_index else (4 if i % 4 == 0 else 30 + i * 3)
                sold = totals[store.id, product.id]
                balance = InventoryBalance(
                    id=uuid.uuid4(),
                    store_id=store.id,
                    product_id=product.id,
                    quantity=ending,
                    reserved=0,
                    safety_stock=5,
                )
                session.add(balance)
                audit = AuditLog(
                    id=uuid.uuid4(),
                    actor_id=users[0].id,
                    action="inventory.demo_seed",
                    entity_type="inventory_balance",
                    entity_id=balance.id,
                    details={
                        "synthetic": True,
                        "opening": sold + ending,
                        "historical_sold": sold,
                        "ending": ending,
                    },
                )
                session.add(audit)
                await session.flush()
                for reason, delta in (
                    ("synthetic opening balance", sold + ending),
                    ("synthetic historical sales", -sold),
                ):
                    session.add(
                        InventoryMovement(
                            store_id=store.id,
                            product_id=product.id,
                            quantity_delta=delta,
                            reason=reason,
                            audit_id=audit.id,
                            actor_id=users[0].id,
                            idempotency_key=f"seed:{store.code}:{product.sku}:{reason}",
                        )
                    )
        for i, store in enumerate(stores):
            order = PurchaseOrder(
                id=uuid.uuid4(),
                store_id=store.id,
                supplier_id=suppliers[i].id,
                created_by=users[1].id,
                status="draft" if i != 1 else "pending",
                total=products[i * 4].cost * 12,
                idempotency_key=f"seed:po:{store.code}",
            )
            session.add(order)
            await session.flush()
            session.add(
                PurchaseOrderItem(
                    purchase_order_id=order.id,
                    product_id=products[i * 4].id,
                    quantity=12,
                    unit_cost=products[i * 4].cost,
                )
            )
        session.add(
            AuditLog(
                actor_id=users[0].id,
                action=SEED_ACTION,
                entity_type="demo",
                details={"synthetic": True, "stores": 3, "products": 12, "days": 90},
            )
        )
    return True


async def seed(settings: Settings, password: str) -> bool:
    url = validate_target(settings, password)
    engine = create_async_engine(url, connect_args={"connect_timeout": 5})
    try:
        async with async_sessionmaker(engine, expire_on_commit=False)() as session:
            return await seed_data(session, password)
    finally:
        await engine.dispose()


if __name__ == "__main__":
    try:
        loop_factory = asyncio.SelectorEventLoop if sys.platform == "win32" else None
        with asyncio.Runner(loop_factory=loop_factory) as runner:
            created = runner.run(seed(Settings(), os.environ.get("RETAILOPS_DEMO_PASSWORD", "")))
        print(
            "Synthetic demo data created." if created else "Demo already seeded; no changes made."
        )
    except ValueError as error:
        raise SystemExit(str(error)) from None
