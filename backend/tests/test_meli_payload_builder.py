import pytest

from app.schemas.drafts import ProductDraftCreate
from app.schemas.publishing import ListingChoice
from app.services.meli.payload_builder import build_item_payload


def complete_draft():
    return ProductDraftCreate(
        title="Stainless Water Bottle",
        description="Leak proof bottle.",
        target_site_id="MLM",
        target_category_id="MLM123",
        price=19.99,
        currency="USD",
        stock=3,
        listing_type_id="gold_special",
        image_urls=["https://example.com/a.jpg"],
    )


def test_build_item_payload_maps_required_fields():
    payload = build_item_payload(
        draft=complete_draft(),
        listing_choice=ListingChoice(
            site_id="MLM", listing_type_id="gold_special", fulfillment="not_full"
        ),
    )
    assert payload["title"] == "Stainless Water Bottle"
    assert payload["listing_type_id"] == "gold_special"
    assert payload["available_quantity"] == 3
    assert payload["pictures"][0]["source"] == "https://example.com/a.jpg"


def test_build_item_payload_rejects_full_fulfillment():
    with pytest.raises(ValueError, match="FULL fulfillment is excluded"):
        build_item_payload(
            draft=complete_draft(),
            listing_choice=ListingChoice(
                site_id="MLM", listing_type_id="gold_special", fulfillment="full"
            ),
        )
