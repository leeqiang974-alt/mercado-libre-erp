from fastapi.testclient import TestClient

from app.main import app


def test_local_frontend_origin_is_allowed():
    client = TestClient(app)
    response = client.options(
        "/api/reviews/local",
        headers={
            "Origin": "http://127.0.0.1:5173",
            "Access-Control-Request-Method": "POST",
        },
    )
    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "http://127.0.0.1:5173"
