"""Global CBT category catalog synchronization and local search."""

import asyncio
from datetime import UTC, datetime

import httpx
from sqlalchemy.orm import Session

from app.services.meli.client import MercadoLibreClient
from app.services.meli.category_i18n import (
    has_chinese,
    translate_category_names_with_ai_batched,
    translate_category_text,
)
from app.services.meli.metadata_cache import get_cached_metadata, upsert_cached_metadata


def category_catalog_key(site_id: str) -> str:
    return f"category_catalog:{site_id.strip().upper()}"


async def complete_category_catalog_translations(
    db: Session, site_id: str, api_key: str, base_url: str, model: str
) -> dict[str, object]:
    """Fill only missing Chinese labels in an already-complete global catalog."""
    site = site_id.strip().upper()
    payload = get_cached_metadata(db, category_catalog_key(site))
    if not isinstance(payload, dict) or payload.get("complete") is not True:
        raise ValueError("category_catalog_not_complete")
    nodes = [node for node in payload.get("nodes", []) if isinstance(node, dict)]
    originals: list[str] = []
    for node in nodes:
        name = str(node.get("name") or "").strip()
        translated = str(node.get("name_zh") or "").strip()
        if name and not has_chinese(translated):
            originals.append(name)
        for index, path_name in enumerate(node.get("path_names", [])):
            existing = (node.get("path_names_zh") or [])
            current = str(existing[index] if index < len(existing) else "").strip()
            if str(path_name).strip() and not has_chinese(current):
                originals.append(str(path_name).strip())
    translations = await translate_category_names_with_ai_batched(
        originals, api_key, base_url, model, batch_size=20
    )
    unresolved: set[str] = set()
    for node in nodes:
        name = str(node.get("name") or "").strip()
        existing_name_zh = str(node.get("name_zh") or "").strip()
        node["name_zh"] = (
            existing_name_zh if has_chinese(existing_name_zh)
            else translations.get(name, translate_category_text(name))
        )
        path_names = [str(value) for value in node.get("path_names", [])]
        existing_path_zh = [str(value) for value in node.get("path_names_zh", [])]
        node["path_names_zh"] = [
            existing_path_zh[index] if index < len(existing_path_zh) and has_chinese(existing_path_zh[index])
            else translations.get(path_name, translate_category_text(path_name))
            for index, path_name in enumerate(path_names)
        ]
        for original, translated in [(name, node["name_zh"]), *zip(path_names, node["path_names_zh"])]:
            if original and not has_chinese(translated):
                unresolved.add(original)
    payload["nodes"] = nodes
    payload["translation_version"] = 5
    payload["translated_by"] = "deepseek+local"
    payload["translation_complete"] = not unresolved
    payload["translation_unresolved_count"] = len(unresolved)
    payload["updated_at"] = datetime.now(UTC).isoformat()
    upsert_cached_metadata(db, category_catalog_key(site), payload)
    return {
        "site": site,
        "nodes": len(nodes),
        "translation_complete": not unresolved,
        "translation_unresolved_count": len(unresolved),
        "translation_candidates": len(set(originals)),
    }


def _norm(value: object) -> str:
    return " ".join(str(value or "").casefold().split())


async def _get_with_retry(client: MercadoLibreClient, path: str) -> dict | list:
    last_error: Exception | None = None
    for attempt in range(4):
        try:
            return await client.get(path)
        except (httpx.RequestError, httpx.HTTPStatusError) as exc:
            last_error = exc
            if attempt == 3:
                raise
            await asyncio.sleep(2 ** attempt)
    raise last_error or RuntimeError("category_request_failed")


async def sync_category_catalog(
    db: Session,
    client: MercadoLibreClient,
    site_id: str,
    api_key: str,
    base_url: str,
    model: str,
    max_nodes: int = 100000,
) -> dict[str, object]:
    site = site_id.strip().upper()
    roots = await _get_with_retry(client, f"/sites/{site}/categories")
    if not isinstance(roots, list):
        raise ValueError("invalid_category_roots_response")
    queue = [(item, None) for item in roots if isinstance(item, dict)]
    seen: set[str] = set()
    nodes: list[dict[str, object]] = []
    semaphore = asyncio.Semaphore(6)

    async def fetch_one(reference: dict, fallback_parent: str | None) -> tuple[dict, list[tuple[dict, str]]]:
        async with semaphore:
            category_id = str(reference.get("id") or "").strip().upper()
            if not category_id:
                return {}, []
            detail = await _get_with_retry(client, f"/categories/{category_id}")
        if not isinstance(detail, dict):
            raise ValueError("invalid_category_detail_response")
        path = [item for item in detail.get("path_from_root", []) if isinstance(item, dict)]
        path_ids = [str(item.get("id") or "").strip().upper() for item in path if item.get("id")]
        path_names = [str(item.get("name") or "").strip() for item in path if item.get("name")]
        children = [item for item in detail.get("children_categories", []) if isinstance(item, dict)]
        node = {
            "site": site,
            "category_id": category_id,
            "parent_id": str(detail.get("parent_id") or fallback_parent or "").strip().upper() or None,
            "path_ids": path_ids or [category_id],
            "path_names": path_names or [str(detail.get("name") or "").strip()],
            "name": str(detail.get("name") or "").strip(),
            "is_leaf": not bool(children),
            "total_items": detail.get("total_items"),
            "locale": site,
            "source": "mercadolibre_api",
        }
        return node, [(child, category_id) for child in children]

    while queue and len(nodes) < max_nodes:
        batch = []
        next_queue = []
        while queue and len(batch) < 6 and len(nodes) + len(batch) < max_nodes:
            reference, fallback_parent = queue.pop(0)
            category_id = str(reference.get("id") or "").strip().upper()
            if category_id and category_id not in seen:
                seen.add(category_id)
                batch.append(fetch_one(reference, fallback_parent))
        fetched = await asyncio.gather(*batch)
        for node, children in fetched:
            if node:
                nodes.append(node)
                next_queue.extend(children)
        queue.extend(next_queue)
    names: list[str] = []
    for node in nodes:
        names.extend([str(node["name"]), *[str(item) for item in node["path_names"]]])
    translations = await translate_category_names_with_ai_batched(
        names, api_key, base_url, model, batch_size=100
    )
    for node in nodes:
        node["name_zh"] = translations.get(str(node["name"]), translate_category_text(node["name"]))
        node["path_names_zh"] = [
            translations.get(str(name), translate_category_text(name))
            for name in node["path_names"]
        ]
    payload = {
        "site": site,
        "complete": not queue,
        "translation_version": 4,
        "translated_by": "deepseek+local" if api_key else "local_fallback",
        "updated_at": datetime.now(UTC).isoformat(),
        "nodes": nodes,
    }
    upsert_cached_metadata(db, category_catalog_key(site), payload)
    return payload


def search_category_catalog(
    payload: dict[str, object], query: str, limit: int = 12
) -> list[dict[str, object]]:
    needle = _norm(query)
    if not needle or payload.get("complete") is not True:
        return []
    terms = [term for term in needle.split() if term]
    ranked: list[tuple[int, dict[str, object]]] = []
    for node in payload.get("nodes", []):
        if not isinstance(node, dict) or node.get("is_leaf") is not True:
            continue
        chinese_name = _norm(str(node.get("name_zh") or ""))
        haystack = _norm(" ".join([
            str(node.get("name") or ""),
            str(node.get("name_zh") or ""),
            *[str(x) for x in node.get("path_names", [])],
            *[str(x) for x in node.get("path_names_zh", [])],
        ]))
        score = sum(3 if term in chinese_name else 2 if term in haystack else 0 for term in terms)
        if score:
            ranked.append((score, node))
    ranked.sort(
        key=lambda item: (
            -item[0],
            -len(item[1].get("path_names", [])),
            str(item[1].get("category_id")),
        )
    )
    return [
        {
            "category_id": node["category_id"],
            "category_name": node["name"],
            "category_name_zh": node.get("name_zh") or node["name"],
            "parent_path": " > ".join(node.get("path_names", [])),
            "parent_path_zh": " > ".join(node.get("path_names_zh", [])),
            "is_leaf": True,
            "source": "category_catalog_cache",
            "match_score": score,
        }
        for score, node in ranked[:limit]
    ]


def browse_category_catalog(
    payload: dict[str, object], category_id: str = ""
) -> dict[str, object]:
    """Build one tree level from the completed flat catalog."""
    nodes = [node for node in payload.get("nodes", []) if isinstance(node, dict)]
    normalized = category_id.strip().upper()
    current = next(
        (node for node in nodes if str(node.get("category_id", "")).upper() == normalized),
        None,
    ) if normalized else None
    children = [
        node for node in nodes
        if str(node.get("parent_id") or "").upper() == (normalized or "")
    ]
    return {
        "category": current,
        "children": children,
        "source": "category_catalog_cache",
        "catalog_complete": True,
        "translation_version": payload.get("translation_version"),
    }
