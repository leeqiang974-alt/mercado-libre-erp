from app.schemas.drafts import ProductDraftCreate
from app.services.ai.review_policy import review_draft_locally


def test_review_blocks_missing_required_publish_fields():
    draft = ProductDraftCreate(title="", target_site_id="MLM", stock=0)
    result = review_draft_locally(draft)
    assert result.decision == "block"
    assert "missing_title" in result.reason_codes
    assert "missing_description" in result.reason_codes


def test_review_requires_human_for_sensitive_claims():
    draft = ProductDraftCreate(
        title="Pain cure supplement",
        description="This product cures pain and treats disease.",
        target_site_id="MLM",
        price=10,
        currency="USD",
        stock=1,
        image_urls=["https://example.com/a.jpg"],
    )
    result = review_draft_locally(draft)
    assert result.decision == "needs_human_review"
    assert "regulated_claim" in result.reason_codes


def test_review_passes_basic_complete_draft():
    draft = ProductDraftCreate(
        title="Stainless Water Bottle",
        description="Leak proof water bottle.",
        target_site_id="MLM",
        price=19.99,
        currency="USD",
        stock=2,
        image_urls=["https://example.com/a.jpg"],
    )
    result = review_draft_locally(draft)
    assert result.decision == "pass"
