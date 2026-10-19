import asyncio
import uuid
from datetime import UTC, datetime, timedelta

import pytest
from fastapi import HTTPException

from app.api.dependencies import require_manager
from app.core.security import hash_password, token_hash, verify_password
from app.db.models import User


def insert_user(connection, role="manager"):
    user_id = uuid.uuid4()
    connection.execute(
        "INSERT INTO users(id,email,name,role,password_hash,active) VALUES (%s,%s,%s,%s,%s,true)",
        [
            user_id,
            f"{role}@retailops.demo",
            "Test User",
            role,
            hash_password("fictional-test-password"),
        ],
    )
    return user_id


def test_password_salts_and_verification():
    first = hash_password("fictional-test-password")
    second = hash_password("fictional-test-password")
    assert first != second
    assert verify_password("fictional-test-password", first)
    assert not verify_password("wrong", first)
    assert not verify_password("wrong", "malformed")
    assert "fictional-test-password" not in first


def test_role_enforcement():
    with pytest.raises(HTTPException) as error:
        asyncio.run(require_manager(User(role="analyst")))
    assert error.value.status_code == 403
    assert asyncio.run(require_manager(User(role="admin"))).role == "admin"


def test_login_me_logout_and_persisted_token_hash(client, db_connection):
    user_id = insert_user(db_connection)
    assert client.get("/api/v1/auth/me").status_code == 401
    assert (
        client.post(
            "/api/v1/auth/login", json={"email": "manager@retailops.demo", "password": "wrong"}
        ).status_code
        == 401
    )
    response = client.post(
        "/api/v1/auth/login",
        json={"email": "MANAGER@retailops.demo", "password": "fictional-test-password"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["token_type"] == "bearer"
    assert data["user"]["id"] == str(user_id)
    assert "password_hash" not in data["user"]
    token = data["access_token"]
    row = db_connection.execute(
        "SELECT token_hash,expires_at FROM sessions WHERE user_id=%s", [user_id]
    ).fetchone()
    assert row[0] == token_hash(token) and row[0] != token
    assert row[1] > datetime.now(UTC)
    headers = {"Authorization": f"Bearer {token}"}
    assert client.get("/api/v1/auth/me", headers=headers).json()["role"] == "manager"
    assert client.post("/api/v1/auth/logout", headers=headers).status_code == 204
    assert client.get("/api/v1/auth/me", headers=headers).status_code == 401
    assert (
        db_connection.execute(
            "SELECT count(*) FROM audit_logs WHERE actor_id=%s", [user_id]
        ).fetchone()[0]
        == 2
    )


def test_expired_and_inactive_sessions_rejected(client, db_connection):
    user_id = insert_user(db_connection)
    token = "fictional-expired-token"
    db_connection.execute(
        "INSERT INTO sessions(id,user_id,token_hash,expires_at) VALUES (%s,%s,%s,%s)",
        [uuid.uuid4(), user_id, token_hash(token), datetime.now(UTC) - timedelta(seconds=1)],
    )
    headers = {"Authorization": f"Bearer {token}"}
    assert client.get("/api/v1/auth/me", headers=headers).status_code == 401
    db_connection.execute(
        "UPDATE sessions SET expires_at=%s WHERE user_id=%s",
        [datetime.now(UTC) + timedelta(hours=1), user_id],
    )
    db_connection.execute("UPDATE users SET active=false WHERE id=%s", [user_id])
    assert client.get("/api/v1/auth/me", headers=headers).status_code == 401
