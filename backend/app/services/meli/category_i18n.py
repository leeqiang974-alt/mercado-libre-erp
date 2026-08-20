"""Operator-facing Chinese labels for Mercado Libre category metadata.

Official category names and ids remain the source of truth. This module only
adds a display label; it never changes the payload sent to Mercado Libre.
"""

import re


PHRASE_TRANSLATIONS = {
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
