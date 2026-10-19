from test_retail_reporting import retail_data as retail_data

from app.core.config import Settings


def test_ai_status_requires_auth_and_is_explicitly_unconfigured(client, retail_data):
    assert client.get("/api/v1/ai/status").status_code == 401
    response = client.get("/api/v1/ai/status", headers=retail_data["headers"]["analyst"])
    assert response.status_code == 200
    assert response.json() == {
        "provider": "disabled",
        "configured": False,
        "model": None,
        "operational_tools": False,
    }


def test_ai_status_uses_app_settings_without_making_model_calls(client, retail_data):
    client.app.state.settings = Settings(
        _env_file=None,
        ai_provider="gemini",
        ai_model="gemini-test-model",
        gemini_api_key="test-only-private-key",
    )
    response = client.get("/api/v1/ai/status", headers=retail_data["headers"]["manager"])
    assert response.status_code == 200
    assert response.json()["configured"] is True
    assert response.json()["model"] == "gemini-test-model"
    assert "test-only-private-key" not in response.text
