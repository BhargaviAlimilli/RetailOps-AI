from fastapi.testclient import TestClient

from app.core.config import Settings
from app.main import create_app


def test_combined_deployment_serves_ui_without_masking_api_or_missing_files(tmp_path):
    (tmp_path / "index.html").write_text("<html>RetailOps shell</html>", encoding="utf-8")
    (tmp_path / "assets").mkdir()
    (tmp_path / "assets" / "app-hashed.js").write_text("// compiled JS", encoding="utf-8")
    app = create_app(
        Settings(
            _env_file=None,
            environment="production",
            database_url="postgresql+psycopg://unused:unused@localhost/unused",
            allowed_hosts=["testserver"],
            web_directory=tmp_path,
        )
    )
    with TestClient(app) as client:
        for path in ("/", "/login", "/assistant", "/documents", "/agents"):
            response = client.get(path)
            assert response.status_code == 200
            assert "RetailOps shell" in response.text
            assert response.headers["cache-control"] == "no-cache"
        asset = client.get("/assets/app-hashed.js")
        assert asset.status_code == 200
        assert "immutable" in asset.headers["cache-control"]
        assert client.get("/api/v1/health").json()["status"] == "ok"
        assert client.get("/api/v1/inventory").status_code == 401
        for path in ("/api/v1/missing", "/docs", "/openapi.json", "/assets/missing.js", "/.env"):
            assert client.get(path).status_code == 404
