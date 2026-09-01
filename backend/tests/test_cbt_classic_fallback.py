from app.api.routes.publishing import _classic_fallback_offers, _merge_global_site_items


def test_retries_only_explicit_premium_listing_type_rejection_as_classic():
    payload = {
        "sites_to_sell": [
            {"site_id": "MLA", "listing_type_id": "gold_pro", "logistic_type": "remote"},
            {"site_id": "MLC", "listing_type_id": "gold_pro", "logistic_type": "remote"},
        ]
    }
    response = {
        "item_id": "CBT123",
        "site_items": [
            {
                "site_id": "MLA",
                "error": {"cause": [{"code": "invalid.listing_type_id", "references": ["gold_pro"]}]},
            },
            {"site_id": "MLC", "error": {"message": "local_rate_limited", "cause": None}},
        ],
    }

    assert _classic_fallback_offers(response, payload) == [
        {"site_id": "MLA", "listing_type_id": "gold_special", "logistic_type": "remote"}
    ]


def test_fallback_response_replaces_only_the_retried_marketplace_row():
    original = {
        "item_id": "CBT123",
        "site_items": [
            {"site_id": "MLA", "error": {"error": "validation_error"}},
            {"site_id": "MLM", "item_id": "MLM1"},
        ],
    }
    fallback = {"site_items": [{"site_id": "MLA", "item_id": "MLA2"}]}

    assert _merge_global_site_items(original, fallback)["site_items"] == [
        {"site_id": "MLA", "item_id": "MLA2"},
        {"site_id": "MLM", "item_id": "MLM1"},
    ]
