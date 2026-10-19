import asyncio

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.core.config import Settings
from app.db.seed import seed_data, validate_target


def test_seed_guards():
    password = "fictional-test-password"
    with pytest.raises(ValueError, match="development"):
        validate_target(Settings(_env_file=None, environment="production"), password)
    with pytest.raises(ValueError, match="retailops_demo"):
        validate_target(
            Settings(_env_file=None, database_url="postgresql+psycopg://localhost/real_data"),
            password,
        )
    with pytest.raises(ValueError, match="12 to 256"):
        validate_target(
            Settings(_env_file=None, database_url="postgresql+psycopg://localhost/retailops_demo"),
            "short",
        )


def test_synthetic_seed_is_repeatable_and_inventory_reconciles(db_url, db_connection):
    async def run():
        engine = create_async_engine(db_url)
        try:
            async with async_sessionmaker(engine)() as session:
                assert await seed_data(session, "fictional-test-password") is True
                assert await seed_data(session, "a-different-test-password") is False
        finally:
            await engine.dispose()

    with asyncio.Runner(loop_factory=asyncio.SelectorEventLoop) as runner:
        runner.run(run())
    assert db_connection.execute("SELECT count(*) FROM stores").fetchone()[0] == 3
    assert db_connection.execute("SELECT count(*) FROM sales").fetchone()[0] == 270
    assert (
        db_connection.execute(
            "SELECT count(*) FROM inventory_balances WHERE quantity=0"
        ).fetchone()[0]
        == 3
    )
    assert db_connection.execute("SELECT count(*) FROM users").fetchone()[0] == 3
    mismatches = db_connection.execute(
        "SELECT b.id FROM inventory_balances b JOIN inventory_movements m "
        "ON m.store_id=b.store_id AND m.product_id=b.product_id "
        "GROUP BY b.id HAVING sum(m.quantity_delta) <> b.quantity"
    ).fetchall()
    assert mismatches == []
