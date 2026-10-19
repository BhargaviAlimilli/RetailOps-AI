from unittest.mock import AsyncMock
from uuid import UUID

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.core.config import Settings
from app.main import create_app


def settings(**overrides):
    return Settings(
        _env_file=None,
        environment="test",
        database_url=None,
        allowed_hosts=["testserver"],
        **overrides,
    )


def test_liveness_without_database():
    with TestClient(create_app(settings())) as client:
        response = client.get("/api/v1/health", headers={"X-Request-ID": "untrusted"})
        assert response.status_code == 200
        assert response.json() == {"status": "ok", "service": "retailops-api"}
        assert UUID(response.headers["X-Request-ID"])
        assert response.headers["X-Content-Type-Options"] == "nosniff"


def test_missing_database_is_not_ready():
    with TestClient(create_app(settings())) as client:
        response = client.get("/api/v1/ready")
        assert response.status_code == 503
        assert response.json() == {"status": "unavailable", "service": "retailops-api"}


def test_successful_readiness_contract():
    app = create_app(settings())
    with TestClient(app) as client:
        app.state.database.is_ready = AsyncMock(return_value=True)
        response = client.get("/api/v1/ready")
        assert response.status_code == 200
        assert response.json()["status"] == "ready"
        app.state.database.is_ready.assert_awaited_once()


@pytest.mark.parametrize(
    "origin,allowed", [("http://localhost:5173", True), ("https://evil.example", False)]
)
def test_cors_only_allows_configured_origins(origin, allowed):
    with TestClient(create_app(settings())) as client:
        response = client.options(
            "/api/v1/health",
            headers={"Origin": origin, "Access-Control-Request-Method": "GET"},
        )
        assert (response.headers.get("access-control-allow-origin") == origin) is allowed


def test_production_disables_documentation():
    app = create_app(
        Settings(
            _env_file=None,
            environment="production",
            database_url=None,
            allowed_hosts=["testserver"],
        )
    )
    with TestClient(app) as client:
        assert client.get("/docs").status_code == 404
        assert client.get("/openapi.json").status_code == 404


def test_rejects_wildcard_cors():
    with pytest.raises(ValidationError, match="explicit HTTP"):
        settings(cors_origins=["*"])


def test_rejects_non_postgres_database():
    with pytest.raises(ValidationError, match="postgresql"):
        Settings(_env_file=None, database_url="sqlite:///demo.db")


def test_invalid_database_url_does_not_expose_password():
    with pytest.raises(ValidationError) as error:
        Settings(_env_file=None, database_url="postgresql://user:dummy-secret@localhost/demo")
    assert "dummy-secret" not in str(error.value)


def test_rejects_untrusted_host():
    with TestClient(create_app(settings())) as client:
        assert (
            client.get("/api/v1/health", headers={"Host": "untrusted.example"}).status_code == 400
        )
