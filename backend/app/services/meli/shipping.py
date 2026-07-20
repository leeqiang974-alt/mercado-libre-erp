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
    options = list_non_full_shipping_options(preferences)
    return options[0] if options else None


def list_non_full_shipping_options(preferences: dict) -> list[NonFullShippingSelection]:
    if not isinstance(preferences, dict):
        return []
    raw_modes = preferences.get("modes")
    raw_modes = raw_modes if isinstance(raw_modes, (list, tuple, set)) else []
    declared_modes = {
        str(mode).strip().lower()
        for mode in raw_modes
        if str(mode).strip()
    }
    logistics_by_mode: dict[str, list[str]] = {}
    inactive_modes: set[str] = set()
    active_modes: set[str] = set()
    raw_logistics = preferences.get("logistics")
    raw_logistics = raw_logistics if isinstance(raw_logistics, (list, tuple)) else []
    for logistic in raw_logistics:
        if not isinstance(logistic, dict):
            continue
        mode = str(logistic.get("mode", "")).strip().lower()
        if not mode:
            continue
        if str(logistic.get("status", "active")).strip().lower() == "inactive":
            inactive_modes.add(mode)
            continue
        active_modes.add(mode)
        declared_modes.add(mode)
        types = logistics_by_mode.setdefault(mode, [])
        raw_types = logistic.get("types")
        raw_types = raw_types if isinstance(raw_types, (list, tuple)) else []
        for raw_type in raw_types:
            if isinstance(raw_type, dict):
                if str(raw_type.get("status", "active")).lower() == "inactive":
                    continue
                logistic_type = raw_type.get("type", "")
            else:
                logistic_type = raw_type
            normalized = str(logistic_type).strip().lower()
            if normalized:
                types.append(normalized)

    options: list[NonFullShippingSelection] = []
    me2_types = set(logistics_by_mode.get("me2", []))
    if "me2" in declared_modes and ("me2" not in inactive_modes or "me2" in active_modes):
        for logistic_type in NON_FULL_LOGISTIC_TYPE_PRIORITY:
            if logistic_type in me2_types:
                options.append(NonFullShippingSelection("me2", logistic_type))
    if "me1" in declared_modes and ("me1" not in inactive_modes or "me1" in active_modes):
        options.append(NonFullShippingSelection("me1", "default"))
    if "not_specified" in declared_modes and (
        "not_specified" not in inactive_modes or "not_specified" in active_modes
    ):
        options.append(NonFullShippingSelection("not_specified", "not_specified"))
    return options
