NON_FULL_SHIPPING_MODE_PRIORITY = ("me2", "me1", "not_specified")


def resolve_non_full_shipping_mode(preferences: dict) -> str | None:
    declared_modes = {
        str(mode).strip().lower()
        for mode in preferences.get("modes", [])
        if str(mode).strip()
    }
    logistics_by_mode: dict[str, list[str]] = {}
    for logistic in preferences.get("logistics", []):
        mode = str(logistic.get("mode", "")).strip().lower()
        if not mode:
            continue
        declared_modes.add(mode)
        types = logistics_by_mode.setdefault(mode, [])
        for raw_type in logistic.get("types", []):
            if isinstance(raw_type, dict):
                if str(raw_type.get("status", "active")).lower() == "inactive":
                    continue
                logistic_type = raw_type.get("type", "")
            else:
                logistic_type = raw_type
            normalized = str(logistic_type).strip().lower()
            if normalized:
                types.append(normalized)

    me2_types = logistics_by_mode.get("me2", [])
    if "me2" in declared_modes and any(item != "fulfillment" for item in me2_types):
        return "me2"
    for mode in NON_FULL_SHIPPING_MODE_PRIORITY[1:]:
        if mode in declared_modes:
            return mode
    return None
