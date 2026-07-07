from app.schemas.drafts import ProductDraftCreate
from app.schemas.publishing import ListingChoice
from app.services.ai.review_policy import review_draft_locally
from app.services.meli.publisher import validate_publish_request


def valid_draft():
    return ProductDraftCreate(
        title="Stainless Water Bottle",
        description="Leak proof bottle.",
        target_site_id="MLM",
        target_category_id="MLM123",
        price=19.99,
        currency="USD",
        stock=3,
        image_urls=["https://example.com/a.jpg"],
    )


def test_publish_gate_allows_reviewed_classic_listing():
    draft = valid_draft()
    result = validate_publish_request(
        draft=draft,
        review=review_draft_locally(draft),
        listing_choice=ListingChoice(
            site_id="MLM", listing_type_id="gold_special", fulfillment="not_full"
        ),
        valid_listing_type_ids=["gold_special", "gold_pro"],
        human_approved=True,
    )
    assert result.allowed is True
    assert result.errors == []


def test_publish_gate_blocks_invalid_listing_type():
    draft = valid_draft()
    result = validate_publish_request(
        draft=draft,
        review=review_draft_locally(draft),
        listing_choice=ListingChoice(site_id="MLM", listing_type_id="gold_full", fulfillment="not_full"),
        valid_listing_type_ids=["gold_special", "gold_pro"],
        human_approved=True,
    )
    assert result.allowed is False
    assert "listing_type_not_available" in result.errors


def test_publish_gate_blocks_without_human_approval():
    draft = valid_draft()
    result = validate_publish_request(
        draft=draft,
        review=review_draft_locally(draft),
        listing_choice=ListingChoice(
            site_id="MLM", listing_type_id="gold_special", fulfillment="not_full"
        ),
        valid_listing_type_ids=["gold_special"],
        human_approved=False,
    )
    assert result.allowed is False
    assert "human_approval_required" in result.errors
