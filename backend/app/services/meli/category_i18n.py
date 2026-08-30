"""Operator-facing Chinese labels for Mercado Libre category metadata.

Official category names and ids remain the source of truth. This module only
adds a display label; it never changes the payload sent to Mercado Libre.
"""

import json
import re
import asyncio

import httpx


def has_chinese(value: object) -> bool:
    return any("\u4e00" <= char <= "\u9fff" for char in str(value or ""))


PHRASE_TRANSLATIONS = {
    "Construction": "建筑与装修",
    "Bathrooms & Restrooms": "浴室与卫生间",
    "Bathroom Fittings": "浴室配件",
    "Handheld Showers": "手持花洒",
    "Shower Heads": "淋浴喷头",
    "Beauty and Personal Care": "美容与个人护理",
    "Hair Salon Listings": "美发沙龙用品",
    "Hair Salon": "美发沙龙",
    "Hair Washing Sinks": "洗发盆",
    "Hygienic Showers": "卫生淋浴",
    # Common MLM Spanish category terms.
    "Alimentos y Bebidas": "食品与饮料",
    "Hogar, Muebles y Jardín": "家居、家具与园艺",
    "Recuerdos, Cotillón y Fiestas": "纪念品、派对用品与节庆",
    "Despensa": "食品储藏",
    "Panadería": "烘焙",
    "Panes": "面包",
    "Panes Dulces y Salados": "甜咸面包",
    "Moldes": "模具",
    "Utensilios de Preparación": "烹饪用具",
    "Desechables para Fiestas": "派对一次性用品",
    "Sierra Empanadas": "馅饼切割器",
    "Cubeteras": "制冰盒",
    "Comidas Preparadas": "熟食",
    "Desayunos y Meriendas": "早餐与茶点",
    "Chipás y Pan de Queso": "芝士面包",
    "Tostadas y Palitos de Pan": "烤面包片与面包棒",
    "Kits de Pastelería": "烘焙套装",
    "Muffin Pans": "玛芬烤盘",
    "Muffin Pan": "玛芬烤盘",
    "Utensillos de Repostería": "烘焙用具",
    "Utensilios de Repostería": "烘焙用具",
    "Silicone Molds": "硅胶模具",
    "Baking Molds": "烘焙模具",
    "Kitchen": "厨房",
    "Cooking": "烹饪",
    "Home": "家居",
    "Bakeware": "烘焙用具",
}

TOKEN_TRANSLATIONS = {
    "Alimentos": "食品",
    "Bebidas": "饮料",
    "Hogar": "家居",
    "Muebles": "家具",
    "Jardín": "园艺",
    "Cocina": "厨房",
    "Utensilios": "用具",
    "Preparación": "烹饪",
    "Panadería": "烘焙",
    "Panes": "面包",
    "Moldes": "模具",
    "Pastelería": "烘焙",
    "Baking": "烘焙",
    "Muffin": "玛芬",
    "Pans": "烤盘",
    "Pan": "烤盘",
    "Silicone": "硅胶",
    "Molds": "模具",
    "Kitchen": "厨房",
    "Cooking": "烹饪",
}

QUERY_TRANSLATIONS = {
    "淋浴": "shower",
    "花洒": "shower",
    "淋浴喷头": "shower head",
    "洗发盆": "hair washing sink",
    "洗头盆": "hair washing sink",
    "卫生间": "bathroom",
    "浴室": "bathroom",
    "浴室配件": "bathroom fittings",
    "建筑": "construction",
    "装修": "construction",
    "头发": "hair",
    "美发": "hair salon",
    "厨房": "kitchen",
    "模具": "molds",
    "烘焙": "bakeware",
}


def translate_category_text(value: object) -> str:
    """Return a conservative Chinese display label for an official name."""
    original = " ".join(str(value or "").split()).strip()
    if not original:
        return ""
    if original in PHRASE_TRANSLATIONS:
        return PHRASE_TRANSLATIONS[original]
    translated = original
    for phrase in sorted(PHRASE_TRANSLATIONS, key=len, reverse=True):
        translated = re.sub(
            rf"(?<![\w]){re.escape(phrase)}(?![\w])",
            PHRASE_TRANSLATIONS[phrase],
            translated,
            flags=re.IGNORECASE,
        )
    for token in sorted(TOKEN_TRANSLATIONS, key=len, reverse=True):
        translated = re.sub(
            rf"(?<![\w]){re.escape(token)}(?![\w])",
            TOKEN_TRANSLATIONS[token],
            translated,
            flags=re.IGNORECASE,
        )
    return translated


def translate_category_query(value: object) -> tuple[str, bool]:
    """Translate supported Chinese search terms without calling an AI model."""
    original = " ".join(str(value or "").split()).strip()
    if not original:
        return "", False
    if all(ord(char) < 128 for char in original):
        return original, True
    translated = original
    matched = False
    for phrase in sorted(QUERY_TRANSLATIONS, key=len, reverse=True):
        if phrase in translated:
            translated = translated.replace(phrase, f" {QUERY_TRANSLATIONS[phrase]} ")
            matched = True
    translated = " ".join(translated.split()).strip()
    return (translated, True) if matched else (original, False)


def add_category_translations(payload: dict) -> dict:
    """Add display-only Chinese labels without mutating official fields."""
    result = dict(payload)
    result["name_zh"] = translate_category_text(result.get("name"))
    path = result.get("path_from_root")
    if isinstance(path, list):
        result["path_from_root_zh"] = [
            {
                **item,
                "name_zh": translate_category_text(item.get("name")),
            }
            for item in path
            if isinstance(item, dict)
        ]
    else:
        result["path_from_root_zh"] = []
    return result


async def translate_category_payload_names(
    payload: dict, api_key: str, base_url: str, model: str
) -> dict:
    """Add Chinese labels to every category node in a tree/detail payload."""
    names: list[str] = []

    def collect(value: object) -> None:
        if isinstance(value, dict):
            if value.get("name"):
                names.append(str(value["name"]))
            for key in ("path_from_root", "children_categories", "children"):
                collect(value.get(key))
        elif isinstance(value, list):
            for item in value:
                collect(item)

    collect(payload)
    translations = await translate_category_names_with_ai(names, api_key, base_url, model)

    def apply(value: object) -> object:
        if isinstance(value, dict):
            result = {key: apply(item) for key, item in value.items()}
            name = str(value.get("name") or "").strip()
            if name:
                result["name_zh"] = translations.get(name, translate_category_text(name))
            path = value.get("path_from_root")
            if isinstance(path, list):
                result["path_from_root_zh"] = apply(path)
            return result
        if isinstance(value, list):
            return [apply(item) for item in value]
        return value

    return apply(payload)


async def translate_category_names_with_ai(values: list[str], api_key: str, base_url: str, model: str) -> dict[str, str]:
    names = list(dict.fromkeys(" ".join(str(value or "").split()).strip() for value in values if str(value or "").strip()))
    result = {name: translate_category_text(name) for name in names}
    # Names that are not already Chinese still need translation. Spanish names
    # commonly contain accented characters, so an ASCII-only check skips valid
    # DeepSeek inputs such as "Categorías" and "Baños".
    pending = [
        name
        for name in names
        if result[name] == name
        and not any("\u4e00" <= char <= "\u9fff" for char in name)
    ]
    if not pending or not api_key:
        return result
    prompt = "Translate each Mercado Libre category name into concise Simplified Chinese. Return JSON object only, preserving every key exactly.\n" + json.dumps(pending, ensure_ascii=False)
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.post(base_url.rstrip("/") + "/chat/completions", headers={"Authorization": "Bearer " + api_key, "Content-Type": "application/json"}, json={"model": model, "temperature": 0, "messages": [{"role": "user", "content": prompt}]})
            response.raise_for_status()
            raw = response.json()["choices"][0]["message"]["content"]
            cleaned = re.sub(r"^\s*```(?:json)?\s*|\s*```\s*$", "", str(raw).strip(), flags=re.IGNORECASE)
            parsed = json.loads(cleaned)
            if isinstance(parsed, dict):
                for key, value in parsed.items():
                    if key in result and isinstance(value, str) and has_chinese(value):
                        result[key] = " ".join(value.split()).strip()
    except (httpx.HTTPError, KeyError, IndexError, TypeError, ValueError, json.JSONDecodeError):
        pass
    return result


async def translate_category_names_with_ai_batched(
    values: list[str], api_key: str, base_url: str, model: str, batch_size: int = 50
) -> dict[str, str]:
    """Translate a large catalog in bounded requests and merge the results."""
    names = list(dict.fromkeys(
        " ".join(str(value or "").split()).strip()
        for value in values
        if str(value or "").strip()
    ))
    merged = {name: translate_category_text(name) for name in names}
    if not api_key:
        return merged
    batches = [
        names[offset : offset + max(1, batch_size)]
        for offset in range(0, len(names), max(1, batch_size))
    ]
    semaphore = asyncio.Semaphore(3)

    async def translate_batch(batch: list[str]) -> dict[str, str]:
        async with semaphore:
            translated = await translate_category_names_with_ai(batch, api_key, base_url, model)
            unresolved = [name for name in batch if not has_chinese(translated.get(name))]
            # JSON responses can omit keys under provider load. Retry only the
            # omitted names so the saved catalog never silently labels English
            # text as translated.
            for attempt in range(2):
                if not unresolved:
                    break
                await asyncio.sleep(attempt + 1)
                retried = await translate_category_names_with_ai(
                    unresolved, api_key, base_url, model
                )
                translated.update(retried)
                unresolved = [name for name in unresolved if not has_chinese(translated.get(name))]
            return translated

    translated_batches = await asyncio.gather(
        *(translate_batch(batch) for batch in batches)
    )
    for translated in translated_batches:
        merged.update(translated)
    return merged
