"""Opt-in read-only integration checks against a migrated disposable demo database."""

import asyncio
import os
import sys

import pytest
from fastapi.testclient import TestClient

from app.core.config import Settings
from app.main import create_app


def test_postgres_readiness_over_http():
    url = os.environ.get("RETAILOPS_TEST_DATABASE_URL")
    if not url:
        pytest.skip("Set RETAILOPS_TEST_DATABASE_URL for real PostgreSQL integration")
    app = create_app(
        Settings(_env_file=None, environment="test", database_url=url, allowed_hosts=["testserver"])
    )
    options = {"loop_factory": asyncio.SelectorEventLoop} if sys.platform == "win32" else {}
    with TestClient(app, backend_options=options) as client:
        response = client.get("/api/v1/ready")
        assert response.status_code == 200
        assert response.json()["status"] == "ready"
