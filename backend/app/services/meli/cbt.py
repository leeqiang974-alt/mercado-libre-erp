from collections.abc import Iterable


SUPPORTED_CBT_REMOTE_SITES = {"MLA", "MLB", "MLC", "MCO", "MLM", "MLU"}
# The authorized-marketplaces endpoint can still report MLU as Remote while
# /global/items rejects it for this seller program. Do not present a target
# that Mercado Libre has declared non-operable.
TEMPORARILY_UNAVAILABLE_CBT_REMOTE_SITES = {"MLU"}


def normalize_cbt_profile(
    seller_id: str,
    user: object,
    marketplaces: object,
    capacity: object,
) -> dict[str, object]:
    user_data = user if isinstance(user, dict) else {}
    marketplace_data = marketplaces if isinstance(marketplaces, dict) else {}
    raw_markets = marketplace_data.get("marketplaces", [])
    if not isinstance(raw_markets, list):
        raw_markets = []
    caps = _capacity_by_market(capacity)
    normalized: list[dict[str, object]] = []
    for item in raw_markets:
        if not isinstance(item, dict):
            continue
        site_id = str(item.get("site_id") or "").strip().upper()
        logistic_type = str(item.get("logistic_type") or "").strip().lower()
        if not site_id:
            continue
        cap = caps.get((site_id, logistic_type), {})
        normalized.append(
            {
                "site_id": site_id,
                "seller_id": str(item.get("user_id") or "").strip(),
                "logistic_type": logistic_type,
                "user_product": bool(item.get("user_product")),
                "listing_count": _number(
                    cap.get(
                        "listing_count",
                        cap.get("total_items", cap.get("count", cap.get("used", cap.get("used_capacity")))),
                    )
                ),
                "listing_limit": _number(
                    cap.get(
                        "listing_limit",
                        cap.get("quota", cap.get("limit", cap.get("capacity", cap.get("maximum")))),
                    )
                ),
                "available": (
                    logistic_type == "remote"
                    and site_id in SUPPORTED_CBT_REMOTE_SITES
                    and site_id not in TEMPORARILY_UNAVAILABLE_CBT_REMOTE_SITES
                ),
            }
        )
    tags = user_data.get("tags", [])
    return {
        "seller_id": seller_id,
        "site_id": "CBT",
        "model": "user_products" if "user_products_seller" in tags else "traditional_global",
        "tags": [str(tag) for tag in tags] if isinstance(tags, list) else [],
        "marketplaces": normalized,
    }


def _capacity_by_market(capacity: object) -> dict[tuple[str, str], dict]:
    rows: Iterable[object]
    if isinstance(capacity, list):
        rows = capacity
    elif isinstance(capacity, dict):
        rows = capacity.get("marketplaces", capacity.get("results", capacity.get("capacities", [])))
        if not isinstance(rows, list):
            rows = []
    else:
        rows = []
    values: dict[tuple[str, str], dict] = {}
    for item in rows:
        if not isinstance(item, dict):
            continue
        site_id = str(item.get("site_id") or "").strip().upper()
        logistic_type = str(item.get("logistic_type") or "").strip().lower()
        if site_id:
            values[(site_id, logistic_type)] = item
    return values


def _number(value: object) -> int | None:
    return value if isinstance(value, int) and not isinstance(value, bool) else None
