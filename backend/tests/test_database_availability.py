import asyncio
from types import SimpleNamespace
from typing import Annotated
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import Depends
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError, OperationalError
from sqlalchemy.exc import TimeoutError as PoolTimeoutError
from sqlalchemy.ext.asyncio import AsyncSession

from app.api import dependencies
from app.core.config import Settings
from app.db import session as database_module
from app.main import create_app


def test_real_postgres_statement_deadline_returns_503(db_url):
    app = create_app(
        Settings(
            _env_file=None,
            database_url=db_url,
            environment="test",
            allowed_hosts=["testserver"],
            database_timeout_seconds=0.05,
        )
    )

    @app.get("/test-statement-deadline")
    async def slow_query(session: Annotated[AsyncSession, Depends(dependencies.get_session)]):
        await session.execute(text("SELECT pg_sleep(0.2)"))
        return {"unexpected": "completed"}

    with TestClient(app, backend_options={"loop_factory": asyncio.SelectorEventLoop}) as client:
        response = client.get("/test-statement-deadline")
    assert response.status_code == 503
    assert response.json() == {"detail": "Database temporarily unavailable"}
    assert "pg_sleep" not in response.text


def test_engine_timeouts_preserve_connection_options(monkeypatch):
    create = MagicMock()
    monkeypatch.setattr(database_module, "create_async_engine", create)
    database_module.Database(
        Settings(
            _env_file=None,
            database_timeout_seconds=2,
            database_url="postgresql+psycopg://localhost/retailops_test?options=-csearch_path%3Dtest_schema",
        )
    )
    arguments = create.call_args.kwargs
    assert arguments["pool_timeout"] == 2
    assert arguments["connect_args"]["connect_timeout"] == 2
    assert "-cstatement_timeout=2000" in arguments["connect_args"]["options"]
    assert "-csearch_path=test_schema" in arguments["connect_args"]["options"]


@pytest.mark.parametrize(
    "error",
    [
        OperationalError("SELECT 1", {}, Exception("fake-private-credential")),
        PoolTimeoutError("fake-private-credential"),
        TimeoutError("fake-private-credential"),
    ],
)
def test_database_outage_returns_sanitized_503(error, monkeypatch, caplog):
    app = create_app(Settings(_env_file=None, database_url=None, allowed_hosts=["testserver"]))
    session = AsyncMock()
    session.scalar.side_effect = error
    context = AsyncMock()
    context.__aenter__.return_value = session
    monkeypatch.setattr(
        dependencies, "async_sessionmaker", MagicMock(return_value=MagicMock(return_value=context))
    )
    with TestClient(app) as client:
        app.state.database.engine = MagicMock()
        response = client.get("/api/v1/auth/me", headers={"Authorization": "Bearer fake-token"})
        app.state.database.engine = None
    assert response.status_code == 503
    assert response.json() == {"detail": "Database temporarily unavailable"}
    assert "fake-private-credential" not in response.text
    assert "fake-private-credential" not in caplog.text


def test_integrity_conflicts_are_not_converted_to_database_outage(monkeypatch):
    context = AsyncMock()
    monkeypatch.setattr(
        dependencies, "async_sessionmaker", MagicMock(return_value=MagicMock(return_value=context))
    )
    request = SimpleNamespace(
        app=SimpleNamespace(state=SimpleNamespace(database=SimpleNamespace(engine=MagicMock())))
    )

    async def run():
        generator = dependencies.get_session(request)
        await anext(generator)
        with pytest.raises(IntegrityError):
            await generator.athrow(IntegrityError("INSERT", {}, Exception("conflict")))

    asyncio.run(run())
