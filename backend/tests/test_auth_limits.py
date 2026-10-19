import asyncio
from threading import BoundedSemaphore, Event
from unittest.mock import AsyncMock

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from app.api.dependencies import get_session
from app.api.v1 import auth
from app.core import auth_limits
from app.core.auth_limits import LoginRateLimiter
from app.core.config import Settings
from app.main import create_app


def test_account_and_peer_limits_expire_without_sleep():
    clock = [100.0]
    limiter = LoginRateLimiter(account_limit=2, ip_limit=3, clock=lambda: clock[0])
    assert limiter.allow("peer1", "USER@example.demo")
    assert limiter.allow("peer2", " user@example.demo ")
    assert not limiter.allow("peer3", "user@example.demo")
    assert limiter.allow("peer1", "another@example.demo")
    assert limiter.allow("peer1", "third@example.demo")
    assert not limiter.allow("peer1", "fourth@example.demo")
    clock[0] += 60
    assert limiter.allow("peer1", "user@example.demo")
    assert len(limiter._buckets) == 2


def test_limiter_has_bounded_storage_and_reclaims_inactive_entries():
    clock = [0.0]
    limiter = LoginRateLimiter(max_buckets=2, clock=lambda: clock[0])
    assert limiter.allow("peer", "one@example.demo")
    assert not limiter.allow("another-peer", "two@example.demo")
    assert len(limiter._buckets) == 2
    assert all("example.demo" not in key for key in limiter._buckets)
    clock[0] = 61
    assert limiter.allow("another-peer", "two@example.demo")
    assert len(limiter._buckets) == 2


def test_http_login_is_rate_limited_without_echoing_credentials(monkeypatch):
    monkeypatch.setattr(auth, "login_limiter", LoginRateLimiter(account_limit=1))
    login = AsyncMock(side_effect=HTTPException(401, "Invalid email or password"))
    monkeypatch.setattr(auth.service, "login", login)
    app = create_app(Settings(_env_file=None, database_url=None, allowed_hosts=["testserver"]))

    async def session_override():
        yield AsyncMock()

    app.dependency_overrides[get_session] = session_override
    body = {"email": "private@example.demo", "password": "fictional-private-password"}
    with TestClient(app) as client:
        assert client.post("/api/v1/auth/login", json=body).status_code == 401
        response = client.post("/api/v1/auth/login", json=body)
    assert response.status_code == 429
    assert response.headers["Retry-After"] == "60"
    assert "private" not in response.text
    assert login.await_count == 1


def test_password_check_capacity_remains_bounded_after_cancellation(monkeypatch):
    release_worker = Event()
    monkeypatch.setattr(auth_limits, "verification_slots", BoundedSemaphore(1))

    async def run():
        started = asyncio.Event()
        finished = asyncio.Event()
        loop = asyncio.get_running_loop()

        def blocking_verify(password, encoded):
            loop.call_soon_threadsafe(started.set)
            try:
                assert release_worker.wait(timeout=5)
                return True
            finally:
                loop.call_soon_threadsafe(finished.set)

        monkeypatch.setattr(auth_limits, "verify_password", blocking_verify)
        first = asyncio.create_task(auth_limits.verify_password_bounded("fake", "fake"))
        await asyncio.wait_for(started.wait(), timeout=5)
        try:
            with pytest.raises(HTTPException) as error:
                await auth_limits.verify_password_bounded("fake", "fake")
            assert error.value.status_code == 429
            first.cancel()
            with pytest.raises(asyncio.CancelledError):
                await first
            with pytest.raises(HTTPException):
                await auth_limits.verify_password_bounded("fake", "fake")
        finally:
            release_worker.set()
            await asyncio.wait_for(finished.wait(), timeout=5)

    asyncio.run(run())
