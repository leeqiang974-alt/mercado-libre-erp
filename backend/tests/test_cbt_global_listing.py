from app.schemas.cbt_listing_config import CbtListingConfigUpsert
from app.schemas.drafts import ProductDraftCreate
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
    assert "pictures" not in payload
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
