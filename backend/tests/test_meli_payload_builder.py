import pytest

from app.schemas.drafts import ProductDraftCreate
from app.schemas.publishing import ListingChoice
from app.services.meli.payload_builder import build_description_payload, build_item_payload


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
    assert "description" not in payload
    assert build_description_payload(complete_draft()) == {
        "plain_text": "Leak proof bottle."
    }


def test_build_item_payload_rejects_full_fulfillment():
    with pytest.raises(ValueError, match="FULL fulfillment is excluded"):
        build_item_payload(
            draft=complete_draft(),
            listing_choice=ListingChoice(
                site_id="MLM", listing_type_id="gold_special", fulfillment="full"
            ),
        )


def test_build_item_payload_rejects_missing_description_before_item_creation():
    with pytest.raises(ValueError, match="Description is required"):
        build_item_payload(
            complete_draft().model_copy(update={"description": "  "}),
            ListingChoice(site_id="MLM", listing_type_id="gold_special"),
        )


def test_build_item_payload_includes_listing_attributes():
    payload = build_item_payload(
        draft=complete_draft(),
        listing_choice=ListingChoice(
            site_id="MLM",
            listing_type_id="gold_special",
            fulfillment="not_full",
            attributes=[{"id": "BRAND", "value_name": "Acme"}],
        ),
    )

    assert payload["attributes"] == [{"id": "BRAND", "value_name": "Acme"}]


def test_build_item_payload_preserves_category_value_ids():
    payload = build_item_payload(
        complete_draft(),
        ListingChoice(
            site_id="MLM",
            listing_type_id="gold_special",
            attributes=[{"id": "COLOR", "value_id": "52028", "value_name": "Blue"}],
        ),
    )

    assert payload["attributes"] == [
        {"id": "COLOR", "value_id": "52028", "value_name": "Blue"}
    ]


def test_build_item_payload_includes_me2_shipping_fields():
    payload = build_item_payload(
        draft=complete_draft(),
        listing_choice=ListingChoice(site_id="MLM", listing_type_id="gold_special"),
        shipping_mode="me2",
        shipping_logistic_type="drop_off",
    )

    assert payload["shipping"] == {
        "mode": "me2",
        "logistic_type": "drop_off",
        "local_pick_up": False,
        "free_shipping": False,
        "free_methods": [],
    }


def test_build_item_payload_does_not_add_me2_fields_to_me1():
    payload = build_item_payload(
        draft=complete_draft(),
        listing_choice=ListingChoice(site_id="MLM", listing_type_id="gold_special"),
        shipping_mode="me1",
        shipping_logistic_type="default",
    )

    assert payload["shipping"] == {
        "mode": "me1",
        "logistic_type": "default",
        "local_pick_up": False,
        "free_shipping": False,
    }
