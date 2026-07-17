from app.services.meli.shipping import resolve_non_full_shipping_mode


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
