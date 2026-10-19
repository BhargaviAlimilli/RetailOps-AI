"""Real PostgreSQL stock and purchase transaction integration checks."""

from concurrent.futures import ThreadPoolExecutor
from uuid import uuid4

from test_retail_reporting import order_body, write_headers
from test_retail_reporting import retail_data as retail_data


def test_adjustment_is_audited_idempotent_and_cannot_overwrite_reserved_stock(
    client, retail_data, db_connection
):
    path = f"/api/v1/inventory/{retail_data['balance']}/adjust"
    key = str(uuid4())
    body = {"delta": -2, "reason": "Cycle count correction"}
    first = client.post(path, json=body, headers=write_headers(retail_data, key))
    assert first.status_code == 200, first.text
    assert first.json()["on_hand"] == 18
    assert (
        client.post(path, json=body, headers=write_headers(retail_data, key)).json()["on_hand"]
        == 18
    )
    assert (
        client.post(
            path, json={**body, "delta": -3}, headers=write_headers(retail_data, key)
        ).status_code
        == 409
    )
    assert (
        client.post(
            path, json={**body, "delta": -100}, headers=write_headers(retail_data)
        ).status_code
        == 409
    )
    assert (
        client.post(path, json=body, headers=write_headers(retail_data, role="analyst")).status_code
        == 403
    )
    assert (
        db_connection.execute(
            "SELECT quantity FROM inventory_balances WHERE id=%s", (retail_data["balance"],)
        ).fetchone()[0]
        == 18
    )
    assert db_connection.execute("SELECT count(*) FROM inventory_movements").fetchone()[0] == 1
    history = client.get(
        path.replace("/adjust", "/movements"), headers=retail_data["headers"]["analyst"]
    )
    assert history.status_code == 200
    assert history.json()[0]["delta"] == -2
    assert history.json()[0]["actor_name"] == "Manager"


def test_purchase_draft_human_approval_receipt_and_retry_are_real(
    client, retail_data, db_connection
):
    key = str(uuid4())
    body = order_body(retail_data)
    response = client.post(
        "/api/v1/purchase-orders", json=body, headers=write_headers(retail_data, key)
    )
    assert response.status_code == 201, response.text
    order = response.json()
    assert order["status"] == "draft"
    assert order["total"] == "17.40"
    replay = client.post(
        "/api/v1/purchase-orders", json=body, headers=write_headers(retail_data, key)
    )
    assert replay.json()["id"] == order["id"]
    path = f"/api/v1/purchase-orders/{order['id']}"
    assert (
        client.post(path + "/receive", json={}, headers=write_headers(retail_data)).status_code
        == 409
    )
    assert (
        client.post(path + "/submit", json={}, headers=write_headers(retail_data)).json()["status"]
        == "pending"
    )
    assert (
        client.post(
            path + "/approve", json={}, headers=write_headers(retail_data, role="analyst")
        ).status_code
        == 403
    )
    approval_key = str(uuid4())
    approved = client.post(
        path + "/approve",
        json={"reason": "Reviewed supplier terms"},
        headers=write_headers(retail_data, approval_key),
    )
    assert approved.status_code == 200, approved.text
    assert approved.json()["status"] == "approved"
    assert len(approved.json()["approvals"]) == 1
    assert (
        client.post(
            path + "/approve",
            json={"reason": "Reviewed supplier terms"},
            headers=write_headers(retail_data, approval_key),
        ).status_code
        == 200
    )
    receipt_key = str(uuid4())
    assert (
        client.post(
            path + "/receive", json={}, headers=write_headers(retail_data, receipt_key)
        ).json()["status"]
        == "received"
    )
    assert (
        client.post(
            path + "/receive", json={}, headers=write_headers(retail_data, receipt_key)
        ).status_code
        == 200
    )
    assert (
        client.post(path + "/receive", json={}, headers=write_headers(retail_data)).status_code
        == 409
    )
    assert (
        db_connection.execute(
            "SELECT quantity FROM inventory_balances WHERE id=%s", (retail_data["balance"],)
        ).fetchone()[0]
        == 26
    )
    assert db_connection.execute("SELECT count(*) FROM inventory_movements").fetchone()[0] == 1
    assert db_connection.execute("SELECT count(*) FROM purchase_order_approvals").fetchone()[0] == 1


def test_purchase_rejects_bad_supplier_quantity_and_untrusted_pricing(client, retail_data):
    body = order_body(retail_data, 5)
    assert (
        client.post(
            "/api/v1/purchase-orders", json=body, headers=write_headers(retail_data)
        ).status_code
        == 422
    )
    body = order_body(retail_data)
    body["items"][0]["unit_cost"] = "0.01"
    assert (
        client.post(
            "/api/v1/purchase-orders", json=body, headers=write_headers(retail_data)
        ).status_code
        == 422
    )
    assert (
        client.post(
            "/api/v1/purchase-orders",
            json=order_body(retail_data),
            headers=write_headers(retail_data, role="analyst"),
        ).status_code
        == 403
    )


def test_parallel_duplicate_adjustments_execute_once(client, retail_data, db_connection):
    path = f"/api/v1/inventory/{retail_data['balance']}/adjust"
    headers = write_headers(retail_data)
    body = {"delta": 3, "reason": "Verified delivery count"}
    with ThreadPoolExecutor(max_workers=2) as pool:
        responses = list(
            pool.map(lambda _: client.post(path, json=body, headers=headers), range(2))
        )
    assert [response.status_code for response in responses] == [200, 200]
    assert (
        db_connection.execute(
            "SELECT quantity FROM inventory_balances WHERE id=%s", (retail_data["balance"],)
        ).fetchone()[0]
        == 23
    )
    assert db_connection.execute("SELECT count(*) FROM inventory_movements").fetchone()[0] == 1


def test_server_order_filter_finds_older_pending_orders(client, retail_data):
    original = client.post(
        "/api/v1/purchase-orders", json=order_body(retail_data), headers=write_headers(retail_data)
    ).json()
    path = f"/api/v1/purchase-orders/{original['id']}/submit"
    assert client.post(path, json={}, headers=write_headers(retail_data)).status_code == 200
    for _ in range(2):
        assert (
            client.post(
                "/api/v1/purchase-orders",
                json=order_body(retail_data),
                headers=write_headers(retail_data),
            ).status_code
            == 201
        )
    response = client.get(
        "/api/v1/purchase-orders?status=pending&page=1&page_size=1",
        headers=retail_data["headers"]["analyst"],
    )
    assert response.status_code == 200, response.text
    assert response.json()["total"] == 1
    assert response.json()["items"][0]["id"] == original["id"]


def test_concurrent_stock_decrements_cannot_consume_reserved_units(
    client, retail_data, db_connection
):
    path = f"/api/v1/inventory/{retail_data['balance']}/adjust"
    body = {"delta": -12, "reason": "Verified count reduction"}
    with ThreadPoolExecutor(max_workers=2) as pool:
        responses = list(
            pool.map(
                lambda _: client.post(path, json=body, headers=write_headers(retail_data)), range(2)
            )
        )
    assert sorted(response.status_code for response in responses) == [200, 409]
    assert (
        db_connection.execute(
            "SELECT quantity FROM inventory_balances WHERE id=%s", (retail_data["balance"],)
        ).fetchone()[0]
        == 8
    )


def test_failed_multi_product_receipt_rolls_back_all_stock_and_status(
    client, retail_data, db_connection
):
    db_connection.execute(
        "INSERT INTO product_suppliers "
        "(id,product_id,supplier_id,unit_cost,supplier_product_code,"
        "minimum_order_quantity,pack_size,lead_time_days) "
        "VALUES (%s,%s,%s,3.10,'SUP-SLOW',1,1,4)",
        (uuid4(), retail_data["slow"], retail_data["supplier"]),
    )
    db_connection.execute(
        "UPDATE inventory_balances SET quantity=2147483647 WHERE id=%s", (retail_data["empty"],)
    )
    body = order_body(retail_data)
    body["items"].append({"product_id": str(retail_data["slow"]), "quantity": 1})
    created = client.post("/api/v1/purchase-orders", json=body, headers=write_headers(retail_data))
    assert created.status_code == 201, created.text
    path = f"/api/v1/purchase-orders/{created.json()['id']}"
    assert (
        client.post(path + "/submit", json={}, headers=write_headers(retail_data)).status_code
        == 200
    )
    assert (
        client.post(path + "/approve", json={}, headers=write_headers(retail_data)).status_code
        == 200
    )
    failed = client.post(path + "/receive", json={}, headers=write_headers(retail_data))
    assert failed.status_code == 409, failed.text
    assert (
        db_connection.execute(
            "SELECT quantity FROM inventory_balances WHERE id=%s", (retail_data["balance"],)
        ).fetchone()[0]
        == 20
    )
    assert (
        db_connection.execute(
            "SELECT status FROM purchase_orders WHERE id=%s", (created.json()["id"],)
        ).fetchone()[0]
        == "approved"
    )
    assert db_connection.execute("SELECT count(*) FROM inventory_movements").fetchone()[0] == 0
