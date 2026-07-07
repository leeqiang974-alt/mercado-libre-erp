from fastapi.testclient import TestClient

from app.main import app


def test_import_review_publish_preview_flow():
    client = TestClient(app)
    imported = client.post(
        "/api/imports/amazon-html",
        json={
            "source_url": "https://www.amazon.com/dp/B000TEST",
            "html": "<span id='productTitle'>Bottle</span><span class='a-price'><span class='a-offscreen'>$9.99</span></span><img id='landingImage' src='https://example.com/a.jpg' />",
            "target_site_id": "MLM",
        },
    )
    assert imported.status_code == 200
    draft = imported.json()
    assert draft["title"] == "Bottle"

    reviewed = client.post("/api/reviews/local", json=draft)
    assert reviewed.status_code == 200
    assert reviewed.json()["decision"] == "pass"

    preview = client.post(
        "/api/publishing/preview",
        json={
            "draft": draft,
            "review": reviewed.json(),
            "listing_choice": {
                "site_id": "MLM",
                "listing_type_id": "gold_special",
                "fulfillment": "not_full",
            },
            "valid_listing_type_ids": ["gold_special", "gold_pro"],
            "human_approved": True,
        },
    )
    assert preview.status_code == 200
    assert preview.json()["allowed"] is True
