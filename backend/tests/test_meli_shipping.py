from app.services.meli.shipping import (
    find_non_full_shipping_selection,
    list_non_full_shipping_options,
    resolve_non_full_shipping,
    resolve_non_full_shipping_mode,
)


def test_me2_is_selected_when_any_non_full_logistic_type_is_active():
    preferences = {
        "modes": ["me2", "me1"],
        "logistics": [
            {
                "mode": "me2",
                "types": [
                    {"type": "fulfillment", "status": "active"},
                    {"type": "drop_off", "status": "active"},
                ],
            }
        ],
    }

    assert resolve_non_full_shipping_mode(preferences) == "me2"
    selection = resolve_non_full_shipping(preferences)
    assert selection is not None
    assert selection.logistic_type == "drop_off"


def test_me1_is_selected_when_me2_only_has_full():
    preferences = {
        "modes": ["me2", "me1"],
        "logistics": [{"mode": "me2", "types": ["fulfillment"]}],
    }

    assert resolve_non_full_shipping_mode(preferences) == "me1"


def test_no_mode_is_selected_when_only_full_or_custom_is_available():
    preferences = {
        "modes": ["me2", "custom"],
        "logistics": [{"mode": "me2", "types": ["fulfillment"]}],
    }

    assert resolve_non_full_shipping_mode(preferences) is None


def test_all_supported_non_full_options_are_listed_in_priority_order():
    preferences = {
        "modes": ["me2", "me1", "not_specified", "custom"],
        "logistics": [
            {
                "mode": "me2",
                "types": ["fulfillment", "self_service", "drop_off"],
            }
        ],
    }

    assert [
        (option.mode, option.logistic_type)
        for option in list_non_full_shipping_options(preferences)
    ] == [
        ("me2", "drop_off"),
        ("me2", "self_service"),
        ("me1", "default"),
        ("not_specified", "not_specified"),
    ]


def test_malformed_or_inactive_shipping_preferences_fail_closed():
    assert list_non_full_shipping_options({"modes": None, "logistics": None}) == []
    assert list_non_full_shipping_options({"modes": ["me2"], "logistics": [None, "bad"]}) == []
    assert list_non_full_shipping_options(
        {
            "modes": ["me1", "not_specified"],
            "logistics": [
                {"mode": "me1", "status": "inactive", "types": None},
                {"mode": "not_specified", "status": "inactive"},
            ],
        }
    ) == []


def test_selected_shipping_lookup_is_normalized_and_never_returns_full():
    preferences = {
        "modes": ["me2"],
        "logistics": [
            {
                "mode": "me2",
                "types": ["fulfillment", "drop_off"],
            }
        ],
    }

    selected = find_non_full_shipping_selection(preferences, " ME2 ", " DROP_OFF ")

    assert selected is not None
    assert (selected.mode, selected.logistic_type) == ("me2", "drop_off")
    assert find_non_full_shipping_selection(preferences, "me2", "fulfillment") is None
