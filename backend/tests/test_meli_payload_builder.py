import pytest

from app.schemas.cbt_listing_config import CbtListingConfigUpsert, CbtMarketplaceOffer
from app.schemas.drafts import ProductDraftCreate
from app.schemas.publishing import ListingChoice
from app.services.meli.payload_builder import (
    build_cbt_user_product_payload,
    build_description_payload,
    build_item_payload,
)


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


def item_condition():
    return {"id": "ITEM_CONDITION", "value_id": "2230284", "value_name": "New"}


def test_build_item_payload_maps_required_fields():
    payload = build_item_payload(
        draft=complete_draft(),
        listing_choice=ListingChoice(
            site_id="MLM",
            listing_type_id="gold_special",
            fulfillment="not_full",
            attributes=[item_condition()],
        ),
    )
    assert payload["title"] == "Stainless Water Bottle"
    assert payload["listing_type_id"] == "gold_special"
    assert payload["available_quantity"] == 3
    assert "condition" not in payload
    assert payload["attributes"] == [item_condition()]
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
            attributes=[item_condition(), {"id": "BRAND", "value_name": "Acme"}],
        ),
    )

    assert payload["attributes"] == [item_condition(), {"id": "BRAND", "value_name": "Acme"}]


def test_build_item_payload_keeps_legacy_condition_with_other_attributes():
    payload = build_item_payload(
        draft=complete_draft().model_copy(update={"condition": "new"}),
        listing_choice=ListingChoice(
            site_id="MLM",
            listing_type_id="gold_special",
            attributes=[{"id": "BRAND", "value_name": "Acme"}],
        ),
    )

    assert payload["condition"] == "new"
    assert payload["attributes"] == [{"id": "BRAND", "value_name": "Acme"}]


def test_build_item_payload_preserves_category_value_ids():
    payload = build_item_payload(
        complete_draft(),
        ListingChoice(
            site_id="MLM",
            listing_type_id="gold_special",
            attributes=[
                item_condition(),
                {"id": "COLOR", "value_id": "52028", "value_name": "Blue"},
            ],
        ),
    )

    assert payload["attributes"] == [
        item_condition(),
        {"id": "COLOR", "value_id": "52028", "value_name": "Blue"}
    ]


def cbt_up_config():
    return CbtListingConfigUpsert(
        store_id=3,
        category_id="CBT1287",
        family_name="Stainless Water Bottle",
        global_title="Stainless Water Bottle 750ml",
        description="Leak proof bottle.",
        price_usd=19.99,
        available_quantity=5,
        attributes=[
            {"id": "ITEM_CONDITION", "value_name": "New"},
            {"id": "SELLER_SKU", "value_name": "BOT-750"},
            {"id": "COLOR", "value_name": "Black"},
            {"id": "PACKAGE_HEIGHT", "value_name": "10"},
            {"id": "PACKAGE_LENGTH", "value_name": "10"},
            {"id": "PACKAGE_WIDTH", "value_name": "10"},
            {"id": "PACKAGE_WEIGHT", "value_name": "500"},
        ],
        sites_to_sell=[
            CbtMarketplaceOffer(
                site_id="MLB", title="Test", listing_type_id="gold_pro"
            )
        ],
    )


def test_build_cbt_user_product_payload_maps_up_model_fields():
    payload = build_cbt_user_product_payload(complete_draft(), cbt_up_config())

    assert "title" not in payload
    assert "variations" not in payload
    assert payload["family_name"] == "Stainless Water Bottle"
    assert payload["category_id"] == "CBT1287"
    assert payload["currency_id"] == "USD"
    assert payload["global_net_proceeds"] == 19.99
    assert payload["available_quantity"] == 5
    assert payload["description"] == {"plain_text": "Leak proof bottle."}
    assert payload["pictures"] == [{"source": "https://example.com/a.jpg"}]
    assert payload["sites_to_sell"] == [{"site_id": "MLB", "logistic_type": "remote"}]
    assert "listing_type_id" not in payload["sites_to_sell"][0]

    attrs = {attr["id"]: attr for attr in payload["attributes"]}
    assert attrs["ITEM_CONDITION"]["value_id"] == "2230284"
    assert attrs["PACKAGE_WEIGHT"]["value_name"] == "500 g"
    assert attrs["COLOR"]["value_name"] == "Black"


def test_build_cbt_user_product_payload_requires_seller_sku_and_package():
    incomplete = cbt_up_config().model_dump()
    incomplete["attributes"] = [{"id": "ITEM_CONDITION", "value_name": "New"}]
    with pytest.raises(ValueError, match="SELLER_SKU|package"):
        build_cbt_user_product_payload(
            complete_draft(), CbtListingConfigUpsert.model_validate(incomplete)
        )


def test_build_cbt_user_product_payload_rejects_empty_family_name():
    with pytest.raises(ValueError, match="family_name"):
        build_cbt_user_product_payload(
            complete_draft(),
            cbt_up_config().model_copy(update={"family_name": "  "}),
        )


def test_build_item_payload_includes_me2_shipping_fields():
    payload = build_item_payload(
        draft=complete_draft(),
        listing_choice=ListingChoice(
            site_id="MLM",
            listing_type_id="gold_special",
            attributes=[item_condition()],
        ),
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
        listing_choice=ListingChoice(
            site_id="MLM",
            listing_type_id="gold_special",
            attributes=[item_condition()],
        ),
        shipping_mode="me1",
        shipping_logistic_type="default",
    )

    assert payload["shipping"] == {
        "mode": "me1",
        "logistic_type": "default",
        "local_pick_up": False,
        "free_shipping": False,
    }
