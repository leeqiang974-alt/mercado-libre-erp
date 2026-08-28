"""Operator-facing Chinese labels for Mercado Libre category metadata.

Official category names and ids remain the source of truth. This module only
adds a display label; it never changes the payload sent to Mercado Libre.
"""

import re


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
    """Translate supported Chinese category keywords before the official search."""
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
