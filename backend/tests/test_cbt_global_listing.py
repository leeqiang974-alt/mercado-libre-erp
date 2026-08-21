from datetime import UTC, datetime
from types import SimpleNamespace

from app.schemas.cbt_listing_config import CbtListingConfigUpsert
from app.schemas.drafts import ProductDraftCreate, ProductDraftRead
from app.services.cbt_listing_configs import to_cbt_listing_config_read
from app.services.meli.cbt import normalize_cbt_profile
from app.services.meli.payload_builder import build_cbt_global_item_payload


def test_traditional_cbt_payload_uses_global_structure_and_remote_markets():
    payload = build_cbt_global_item_payload(
        ProductDraftCreate(
            title="Source title",
            description="Source description",
            image_urls=["https://example.com/main.jpg"],
        ),
        CbtListingConfigUpsert.model_validate(
            {
                "store_id": 2,
                "category_id": "CBT432923",
                "family_name": "Silicone mold family",
                "global_title": "Reusable Silicone Mold",
                "description": "English global description",
                "price_usd": 9.99,
                "available_quantity": 10,
                "attributes": [
                    {"id": "ITEM_CONDITION", "value_name": "New"},
                    {"id": "SELLER_SKU", "value_name": "SKU-100"},
                    {"id": "PACKAGE_HEIGHT", "value_name": "5 cm"},
                    {"id": "PACKAGE_LENGTH", "value_name": "10 cm"},
                    {"id": "PACKAGE_WIDTH", "value_name": "8 cm"},
                    {"id": "PACKAGE_WEIGHT", "value_name": "100 g"},
                ],
                "sale_terms": [{"id": "WARRANTY_TYPE", "value_name": "No warranty"}],
                "sites_to_sell": [
                    {
                        "site_id": "MLM",
                        "title": "Molde de silicona reutilizable",
                        "listing_type_id": "gold_pro",
                    }
                ],
            }
        ),
    )

    assert payload["currency_id"] == "USD"
    assert payload["family_name"] == "Silicone mold family"
    assert payload["description"] == {"plain_text": "English global description"}
    assert payload["pictures"] == [{"source": "https://example.com/main.jpg"}]
    assert payload["sites_to_sell"] == [
        {
            "site_id": "MLM",
            "logistic_type": "remote",
            "listing_type_id": "gold_pro",
            "title": "Molde de silicona reutilizable",
            "pictures": [{"source": "https://example.com/main.jpg"}],
        }
    ]


def test_cbt_profile_marks_only_remote_supported_markets_available():
    profile = normalize_cbt_profile(
        "2942677449",
        {"tags": ["normal"]},
        {
            "marketplaces": [
                {"user_id": 1, "site_id": "MLM", "logistic_type": "remote"},
                {"user_id": 2, "site_id": "MLM", "logistic_type": "fulfillment"},
            ]
        },
        {"marketplaces": [{"site_id": "MLM", "logistic_type": "remote", "total_items": 78, "quota": 1000}]},
    )

    assert profile["model"] == "traditional_global"
    assert profile["marketplaces"][0]["available"] is True
    assert profile["marketplaces"][0]["listing_count"] == 78
    assert profile["marketplaces"][1]["available"] is False


def test_cbt_profile_marks_uruguay_unavailable_for_international_dropshipping():
    profile = normalize_cbt_profile(
        "2942677449", {"tags": ["normal"]},
        {"marketplaces": [{"user_id": 3, "site_id": "MLU", "logistic_type": "remote"}]}, [],
    )

    assert profile["marketplaces"][0]["available"] is False


def test_cbt_payload_normalizes_condition_and_package_units():
    payload = build_cbt_global_item_payload(
        ProductDraftCreate(
            title="Reusable Silicone Mold",
            description="English description",
            image_urls=["https://example.com/main.jpg"],
        ),
        CbtListingConfigUpsert.model_validate(
            {
                "store_id": 2,
                "category_id": "CBT432923",
                "family_name": "xy000013",
                "global_title": "Reusable Silicone Mold",
                "description": "English description",
                "price_usd": 9.99,
                "available_quantity": 999,
                "attributes": [
                    {"id": "ITEM_CONDITION", "value_name": "new"},
                    {"id": "SELLER_SKU", "value_name": "xy000013"},
                    {"id": "PACKAGE_LENGTH", "value_name": "25"},
                    {"id": "PACKAGE_WIDTH", "value_name": "25"},
                    {"id": "PACKAGE_HEIGHT", "value_name": "5"},
                    {"id": "PACKAGE_WEIGHT", "value_name": "250"},
                ],
                "sites_to_sell": [{"site_id": "MLM", "title": "Reusable Silicone Mold", "listing_type_id": "gold_special"}],
            }
        ),
    )

    attributes = {item["id"]: item for item in payload["attributes"]}
    assert attributes["ITEM_CONDITION"]["value_id"] == "2230284"
    assert attributes["PACKAGE_LENGTH"]["value_name"] == "25 cm"
    assert attributes["PACKAGE_WEIGHT"]["value_name"] == "250 g"


def test_cbt_payload_rejects_more_than_twelve_pictures():
    config = CbtListingConfigUpsert.model_validate(
        {
            "store_id": 2, "category_id": "CBT432923", "family_name": "xy000013",
            "global_title": "Reusable Silicone Mold", "description": "English description",
            "price_usd": 9.99, "available_quantity": 999,
            "attributes": [
                {"id": "ITEM_CONDITION", "value_name": "New"},
                {"id": "SELLER_SKU", "value_name": "xy000013"},
                {"id": "PACKAGE_LENGTH", "value_name": "25 cm"},
                {"id": "PACKAGE_WIDTH", "value_name": "25 cm"},
                {"id": "PACKAGE_HEIGHT", "value_name": "5 cm"},
                {"id": "PACKAGE_WEIGHT", "value_name": "250 g"},
            ],
            "sites_to_sell": [{"site_id": "MLM", "title": "Reusable Silicone Mold", "listing_type_id": "gold_special"}],
        }
    )

    try:
        build_cbt_global_item_payload(
            ProductDraftCreate(
                title="Reusable Silicone Mold", description="English description",
                image_urls=[f"https://example.com/{number}.jpg" for number in range(13)],
            ),
            config,
        )
    except ValueError as error:
        assert "at most 12 pictures" in str(error)
    else:
        raise AssertionError("Expected a 12-picture validation error")


def test_cbt_payload_keeps_seller_warranty_type_and_time():
    payload = build_cbt_global_item_payload(
        ProductDraftCreate(
            title="Reusable Silicone Mold", description="English description",
            image_urls=["https://example.com/main.jpg"],
        ),
        CbtListingConfigUpsert.model_validate(
            {
                "store_id": 2, "category_id": "CBT432923", "family_name": "xy000013",
                "global_title": "Reusable Silicone Mold", "description": "English description",
                "price_usd": 20, "available_quantity": 999,
                "attributes": [
                    {"id": "ITEM_CONDITION", "value_name": "New"}, {"id": "SELLER_SKU", "value_name": "xy000013"},
                    {"id": "PACKAGE_LENGTH", "value_name": "25 cm"}, {"id": "PACKAGE_WIDTH", "value_name": "25 cm"},
                    {"id": "PACKAGE_HEIGHT", "value_name": "5 cm"}, {"id": "PACKAGE_WEIGHT", "value_name": "250 g"},
                ],
                "sale_terms": [
                    {"id": "WARRANTY_TYPE", "value_id": "2230280", "value_name": "Seller warranty"},
                    {"id": "WARRANTY_TIME", "value_name": "7 days"},
                ],
                "sites_to_sell": [{"site_id": "MLM", "title": "Reusable Silicone Mold", "listing_type_id": "gold_special"}],
            }
        ),
    )

    assert payload["sale_terms"] == [
        {"id": "WARRANTY_TYPE", "value_id": "2230280", "value_name": "Seller warranty"},
        {"id": "WARRANTY_TIME", "value_name": "7 days"},
    ]


def test_cbt_config_response_accepts_the_saved_draft_snapshot():
    """Saving must not re-serialize a ProductDraftRead as an ORM model."""
    draft = ProductDraftRead(
        id=14,
        title="Reusable Silicone Mold",
        description="English description",
        brand="Unbranded",
        target_site_id="CBT",
        target_category_id="CBT30046",
        condition="new",
        source_price=None,
        source_currency="USD",
        price=12.5,
        currency="USD",
        stock=999,
        listing_type_id="gold_special",
        image_urls=[],
        video_urls=[],
        attributes=[],
        status="draft",
        risk_status="unreviewed",
        content_version=8,
    )
    now = datetime.now(UTC)
    config = SimpleNamespace(
        id=1,
        product_draft_id=14,
        store_id=2,
        category_id="CBT30046",
        family_name="xy000014",
        global_title=draft.title,
        description=draft.description,
        price_usd=12.5,
        available_quantity=999,
        attributes_json=[],
        sale_terms_json=[],
        sites_to_sell_json=[
            {"site_id": "MLM", "title": draft.title, "listing_type_id": "gold_special"}
        ],
        draft_content_version=8,
        created_at=now,
        updated_at=now,
    )

    result = to_cbt_listing_config_read(config, draft)

    assert result.draft.id == 14
    assert result.draft.content_version == 8
