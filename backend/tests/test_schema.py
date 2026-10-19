import uuid

import psycopg
import pytest


def test_migrated_schema_constraints_and_utc(db_connection):
    store_id, category_id, product_id = [uuid.uuid4() for _ in range(3)]
    db_connection.execute(
        "INSERT INTO stores(id,code,name) VALUES (%s,'TEST','Test Store')", [store_id]
    )
    db_connection.execute(
        "INSERT INTO categories(id,name) VALUES (%s,'Test Category')", [category_id]
    )
    db_connection.execute(
        "INSERT INTO products(id,sku,name,category_id,price,cost,reorder_point,active) "
        "VALUES (%s,'SKU','Product',%s,12.50,5.00,10,true)",
        [product_id, category_id],
    )
    with pytest.raises(psycopg.errors.CheckViolation):
        db_connection.execute(
            "INSERT INTO inventory_balances(id,store_id,product_id,quantity,reserved,safety_stock) "
            "VALUES (%s,%s,%s,2,3,5)",
            [uuid.uuid4(), store_id, product_id],
        )
    with pytest.raises(psycopg.errors.ForeignKeyViolation):
        db_connection.execute(
            "INSERT INTO inventory_balances(id,store_id,product_id,quantity,reserved,safety_stock) "
            "VALUES (%s,%s,%s,5,0,5)",
            [uuid.uuid4(), uuid.uuid4(), product_id],
        )
    row = db_connection.execute(
        "SELECT price,created_at FROM products WHERE id = %s", [product_id]
    ).fetchone()
    assert str(row[0]) == "12.50"
    assert row[1].tzinfo is not None
    assert db_connection.execute("SELECT version_num FROM alembic_version").fetchone()[0] == "0003"
