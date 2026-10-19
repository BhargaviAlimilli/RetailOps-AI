"""Real PostgreSQL API checks with per-test isolated migrated schemas."""

import secrets
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import uuid4

import pytest

from app.core.security import token_hash


@pytest.fixture
def retail_data(db_connection):
    connection = db_connection
    identifiers = {
        name: uuid4()
        for name in ["store", "category", "product", "slow", "supplier", "balance", "empty"]
    }
    headers = {}
    for role in ("manager", "analyst"):
        user_id = uuid4()
        token = secrets.token_urlsafe(32)
        connection.execute(
            "INSERT INTO users (id,email,name,role,password_hash,active) VALUES "
            "(%s,%s,%s,%s,%s,true)",
            (user_id, f"{role}@test.example", role.title(), role, "test-session-only-no-password"),
        )
        connection.execute(
            "INSERT INTO sessions (id,user_id,token_hash,expires_at) VALUES (%s,%s,%s,%s)",
            (uuid4(), user_id, token_hash(token), datetime.now(UTC) + timedelta(hours=1)),
        )
        headers[role] = {"Authorization": f"Bearer {token}"}
    connection.execute(
        "INSERT INTO stores(id,code,name) VALUES (%s,'TEST','Test Store')", (identifiers["store"],)
    )
    connection.execute(
        "INSERT INTO categories(id,name) VALUES (%s,'Test Category')", (identifiers["category"],)
    )
    for key, sku, name in [
        ("product", "TEST-1", "Test product"),
        ("slow", "SLOW-1", "Unsold product"),
    ]:
        connection.execute(
            "INSERT INTO "
            "products(id,sku,name,category_id,price,cost,reorder_point,active) VALUES "
            "(%s,%s,%s,%s,5.20,3.10,10,true)",
            (identifiers[key], sku, name, identifiers["category"]),
        )
    connection.execute(
        "INSERT INTO suppliers(id,name,email,lead_time_days) VALUES (%s,'Test "
        "supplier','supplier@test.example',4)",
        (identifiers["supplier"],),
    )
    connection.execute(
        "INSERT INTO product_suppliers "
        "(id,product_id,supplier_id,unit_cost,supplier_product_code,"
        "minimum_order_quantity,pack_size,lead_time_days) VALUES "
        "(%s,%s,%s,2.90,'SUP-1',6,3,4)",
        (uuid4(), identifiers["product"], identifiers["supplier"]),
    )
    for balance, product, quantity in [("balance", "product", 20), ("empty", "slow", 0)]:
        connection.execute(
            "INSERT INTO "
            "inventory_balances(id,store_id,product_id,quantity,reserved,safety_stock) "
            "VALUES (%s,%s,%s,%s,%s,5)",
            (
                identifiers[balance],
                identifiers["store"],
                identifiers[product],
                quantity,
                4 if quantity else 0,
            ),
        )
    for day, quantity in [(13, 10), (15, 2), (16, 3)]:
        sale_id = uuid4()
        connection.execute(
            "INSERT INTO sales(id,store_id,sold_at,total) VALUES (%s,%s,%s,%s)",
            (
                sale_id,
                identifiers["store"],
                datetime(2026, 10, day, 12, tzinfo=UTC),
                str(Decimal("5.20") * quantity),
            ),
        )
        connection.execute(
            "INSERT INTO sale_items(id,sale_id,product_id,quantity,unit_price,unit_cost) "
            "VALUES (%s,%s,%s,%s,5.20,3.10)",
            (uuid4(), sale_id, identifiers["product"], quantity),
        )
    return {**identifiers, "headers": headers}


def write_headers(data, key=None, role="manager"):
    return {**data["headers"][role], "Idempotency-Key": key or str(uuid4())}


def order_body(data, quantity=6):
    return {
        "store_id": str(data["store"]),
        "supplier_id": str(data["supplier"]),
        "items": [{"product_id": str(data["product"]), "quantity": quantity}],
    }


def test_real_dashboard_money_periods_and_zero_sale_products(client, retail_data):
    response = client.get(
        "/api/v1/dashboard?start_date=2026-10-15&end_date=2026-10-16",
        headers=retail_data["headers"]["analyst"],
    )
    assert response.status_code == 200, response.text
    data = response.json()
    assert data["revenue"] == "26.00"
    assert data["gross_profit"] == "10.50"
    assert data["gross_margin"] == "40.38"
    assert data["average_order_value"] == "13.00"
    assert data["order_count"] == 2
    assert data["revenue_change_percent"] == "-50.00"
    assert data["out_of_stock_count"] == 1
    assert data["inventory_valuation"] == "62.00"
    assert len(data["trend"]) == 2
    assert data["slow_products"][0]["quantity"] == 0
    bad = client.get(
        "/api/v1/dashboard?start_date=2026-10-16&end_date=2026-10-15",
        headers=retail_data["headers"]["manager"],
    )
    assert bad.status_code == 422


def test_read_auth_search_and_pagination(client, retail_data):
    assert client.get("/api/v1/products").status_code == 401
    headers = retail_data["headers"]["analyst"]
    response = client.get("/api/v1/products?page_size=1&page=2", headers=headers)
    assert response.status_code == 200, response.text
    assert response.json()["total"] == 2
    assert len(response.json()["items"]) == 1
    assert client.get("/api/v1/products?q=%25", headers=headers).json()["total"] == 0
    assert client.get("/api/v1/products?page_size=10000", headers=headers).status_code == 422
    sales = client.get("/api/v1/sales?start_date=2026-10-15&end_date=2026-10-16", headers=headers)
    assert sales.status_code == 200, sales.text
    assert sales.json()["total"] == 2


def test_manager_can_create_product_and_analyst_cannot(client, retail_data, db_connection):
    body = {
        "sku": "NEW-1",
        "name": "New catalog product",
        "category_id": str(retail_data["category"]),
        "unit_cost": "2.35",
        "unit_price": "4.60",
        "reorder_point": 8,
    }
    assert (
        client.post(
            "/api/v1/products", json=body, headers=retail_data["headers"]["analyst"]
        ).status_code
        == 403
    )
    result = client.post("/api/v1/products", json=body, headers=retail_data["headers"]["manager"])
    assert result.status_code == 201, result.text
    assert result.json()["unit_cost"] == "2.35"
    assert (
        db_connection.execute(
            "SELECT quantity FROM inventory_balances WHERE product_id=%s", (result.json()["id"],)
        ).fetchone()[0]
        == 0
    )
    assert (
        client.post(
            "/api/v1/products", json=body, headers=retail_data["headers"]["manager"]
        ).status_code
        == 409
    )


def test_concurrent_duplicate_sku_returns_conflict(client, retail_data, db_connection):
    body = {
        "sku": "CONCURRENT-1",
        "name": "Concurrent product",
        "category_id": str(retail_data["category"]),
        "unit_cost": "1.10",
        "unit_price": "2.20",
    }
    from concurrent.futures import ThreadPoolExecutor

    with ThreadPoolExecutor(max_workers=2) as pool:
        responses = list(
            pool.map(
                lambda _: client.post(
                    "/api/v1/products", json=body, headers=retail_data["headers"]["manager"]
                ),
                range(2),
            )
        )
    assert sorted(result.status_code for result in responses) == [201, 409]
    assert (
        db_connection.execute("SELECT count(*) FROM products WHERE sku='CONCURRENT-1'").fetchone()[
            0
        ]
        == 1
    )


def test_validation_error_does_not_echo_password(client):
    secret = "test-only-private-value" * 20
    response = client.post("/api/v1/auth/login", json={"email": "a@b.example", "password": secret})
    assert response.status_code == 422
    assert "test-only-private-value" not in response.text
    assert "input" not in response.json()["detail"][0]


def test_store_comparison_does_not_merge_matching_names(client, retail_data, db_connection):
    store_id, sale_id = uuid4(), uuid4()
    db_connection.execute(
        "INSERT INTO stores(id,code,name) VALUES (%s,'OTHER','Test Store')", (store_id,)
    )
    db_connection.execute(
        "INSERT INTO sales(id,store_id,sold_at,total) VALUES (%s,%s,%s,5.20)",
        (sale_id, store_id, datetime(2026, 10, 15, 12, tzinfo=UTC)),
    )
    db_connection.execute(
        "INSERT INTO sale_items(id,sale_id,product_id,quantity,unit_price,unit_cost) "
        "VALUES (%s,%s,%s,1,5.20,3.10)",
        (uuid4(), sale_id, retail_data["product"]),
    )
    response = client.get(
        "/api/v1/dashboard?start_date=2026-10-15&end_date=2026-10-16",
        headers=retail_data["headers"]["manager"],
    )
    assert response.status_code == 200, response.text
    assert len(response.json()["by_store"]) == 2


def test_daily_revenue_is_utc_even_with_non_utc_database_session(
    db_url, retail_data, db_connection
):
    import asyncio

    from fastapi.testclient import TestClient
    from sqlalchemy.engine import make_url

    from app.core.config import Settings
    from app.main import create_app

    db_connection.execute(
        "UPDATE sales SET sold_at = sold_at + interval '11 hours 30 minutes' "
        "WHERE extract(day from sold_at) IN (15,16)"
    )
    url = make_url(db_url)
    options = url.query.get("options", "") + " -ctimezone=Asia/Kolkata"
    value = url.update_query_dict({"options": options}).render_as_string(hide_password=False)
    application = create_app(
        Settings(
            _env_file=None, environment="test", database_url=value, allowed_hosts=["testserver"]
        )
    )
    with TestClient(
        application, backend_options={"loop_factory": asyncio.SelectorEventLoop}
    ) as client:
        response = client.get(
            "/api/v1/dashboard?start_date=2026-10-15&end_date=2026-10-16",
            headers=retail_data["headers"]["manager"],
        )
    assert response.status_code == 200, response.text
    assert [point["revenue"] for point in response.json()["trend"]] == ["10.40", "15.60"]
