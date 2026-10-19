"""Real PostgreSQL integration isolation: dedicated database and unique per-test schemas."""

import os
import subprocess
import sys
import uuid
from pathlib import Path

import psycopg
import pytest
from fastapi.testclient import TestClient
from psycopg import sql
from sqlalchemy.engine import make_url

from app.core.config import Settings
from app.main import create_app


@pytest.fixture
def db_url():
    settings = Settings()
    if settings.database_url is None:
        pytest.skip("Real PostgreSQL integration requires RETAILOPS_DATABASE_URL")
    source = make_url(settings.database_url.get_secret_value())
    if source.database not in {"retailops_demo", "retailops_test"}:
        pytest.fail("Integration tests require a disposable retailops_demo/test server")
    test_url = source.set(database="retailops_test")
    admin_url = source.set(drivername="postgresql", database="postgres")
    with psycopg.connect(admin_url.render_as_string(hide_password=False), autocommit=True) as admin:
        if not admin.execute(
            "SELECT 1 FROM pg_database WHERE datname = 'retailops_test'"
        ).fetchone():
            admin.execute("CREATE DATABASE retailops_test")
    schema = "test_" + uuid.uuid4().hex
    plain_url = test_url.set(drivername="postgresql").render_as_string(hide_password=False)
    # Extensions belong to the durable public schema, not a schema dropped by another test.
    # Serialize extension setup across concurrent pytest processes on this disposable DB.
    with psycopg.connect(plain_url) as connection:
        connection.execute("SELECT pg_advisory_xact_lock(842718202)")
        connection.execute("CREATE EXTENSION IF NOT EXISTS vector WITH SCHEMA public")
        connection.execute("ALTER EXTENSION vector SET SCHEMA public")
    with psycopg.connect(plain_url, autocommit=True) as connection:
        connection.execute(sql.SQL("CREATE SCHEMA {}").format(sql.Identifier(schema)))
    url = test_url.update_query_dict(
        {"options": f"-csearch_path={schema},public"}
    ).render_as_string(hide_password=False)
    try:
        environment = os.environ.copy()
        environment["RETAILOPS_DATABASE_URL"] = url
        subprocess.run(
            [sys.executable, "-m", "alembic", "upgrade", "head"],
            cwd=Path(__file__).parents[1],
            env=environment,
            check=True,
            capture_output=True,
        )
        yield url
    finally:
        with psycopg.connect(plain_url, autocommit=True) as connection:
            connection.execute(sql.SQL("DROP SCHEMA {} CASCADE").format(sql.Identifier(schema)))


@pytest.fixture
def db_connection(db_url):
    """Sync connection, autocommit; committed changes are visible to HTTP clients."""
    url = make_url(db_url).set(drivername="postgresql").render_as_string(hide_password=False)
    with psycopg.connect(url, autocommit=True) as connection:
        yield connection


@pytest.fixture
def client(db_url):
    settings = Settings(
        _env_file=None, environment="test", database_url=db_url, allowed_hosts=["testserver"]
    )
    app = create_app(settings)
    with TestClient(
        app, backend_options={"loop_factory": __import__("asyncio").SelectorEventLoop}
    ) as client:
        yield client
