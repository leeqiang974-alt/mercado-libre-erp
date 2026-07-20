from dataclasses import dataclass


NON_FULL_SHIPPING_MODE_PRIORITY = ("me2", "me1", "not_specified")
NON_FULL_LOGISTIC_TYPE_PRIORITY = (
    "drop_off",
    "cross_docking",
    "xd_drop_off",
    "self_service",
    "turbo",
)


@dataclass(frozen=True)
class NonFullShippingSelection:
    mode: str
    logistic_type: str


def resolve_non_full_shipping_mode(preferences: dict) -> str | None:
    selection = resolve_non_full_shipping(preferences)
    return selection.mode if selection else None


def resolve_non_full_shipping(preferences: dict) -> NonFullShippingSelection | None:
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

    me2_types = set(logistics_by_mode.get("me2", []))
    if "me2" in declared_modes:
        for logistic_type in NON_FULL_LOGISTIC_TYPE_PRIORITY:
            if logistic_type in me2_types:
                return NonFullShippingSelection("me2", logistic_type)
    if "me1" in declared_modes:
        return NonFullShippingSelection("me1", "default")
    if "not_specified" in declared_modes:
        return NonFullShippingSelection("not_specified", "not_specified")
    return None
