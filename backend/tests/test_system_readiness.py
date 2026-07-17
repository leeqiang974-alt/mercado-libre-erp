from fastapi.testclient import TestClient

from app.main import app


def test_system_readiness_reports_real_integration_state_without_secrets():
    response = TestClient(app).get("/api/system/readiness")

    assert response.status_code == 200
    data = response.json()
    assert data["database"] is True
    assert data["amazon_collector"] is True
    assert isinstance(data["mercado_libre"]["credentials_configured"], bool)
    assert isinstance(data["mercado_libre"]["connected_stores"], int)
    assert isinstance(data["ai"]["claude_configured"], bool)
    assert isinstance(data["ai"]["nvidia_configured"], bool)
    assert set(data["counts"]) == {"drafts", "collection_jobs", "publish_jobs"}
    serialized = response.text.lower()
    assert "api_key" not in serialized
    assert "client_secret" not in serialized
