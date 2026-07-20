import ast
import json
import re
from urllib.parse import urlparse

from bs4 import BeautifulSoup


def _text(node) -> str:
    return " ".join(node.get_text(" ", strip=True).split()) if node else ""


DOMAIN_CURRENCIES = {
    "amazon.com": "USD",
    "amazon.ca": "CAD",
    "amazon.com.mx": "MXN",
    "amazon.com.br": "BRL",
    "amazon.co.uk": "GBP",
    "amazon.de": "EUR",
    "amazon.fr": "EUR",
    "amazon.it": "EUR",
    "amazon.es": "EUR",
    "amazon.nl": "EUR",
    "amazon.co.jp": "JPY",
    "amazon.com.au": "AUD",
    "amazon.in": "INR",
    "amazon.sg": "SGD",
    "amazon.ae": "AED",
    "amazon.sa": "SAR",
}

ASIN_PATTERN = re.compile(
    r"/(?:dp|gp/product|gp/aw/d)/([A-Z0-9]{10})(?:[/?]|$)",
    re.IGNORECASE,
)

EXPLICIT_CURRENCIES = {
    "US$": "USD",
    "USD": "USD",
    "MX$": "MXN",
    "MXN": "MXN",
    "CDN$": "CAD",
    "CA$": "CAD",
    "CAD": "CAD",
    "A$": "AUD",
    "AUD": "AUD",
    "R$": "BRL",
    "BRL": "BRL",
    "£": "GBP",
    "GBP": "GBP",
    "€": "EUR",
    "EUR": "EUR",
    "¥": "JPY",
    "￥": "JPY",
    "JPY": "JPY",
}

WEIGHT_UNITS = {
    "lb": "lb", "lbs": "lb", "pound": "lb", "pounds": "lb",
    "oz": "oz", "ounce": "oz", "ounces": "oz",
    "kg": "kg", "kilogram": "kg", "kilograms": "kg",
    "g": "g", "gram": "g", "grams": "g",
}
DIMENSION_UNITS = {
    "in": "in", "inch": "in", "inches": "in",
    "cm": "cm", "centimeter": "cm", "centimeters": "cm",
    "mm": "mm", "millimeter": "mm", "millimeters": "mm",
    "ft": "ft", "foot": "ft", "feet": "ft",
    "m": "m", "meter": "m", "meters": "m",
}
COMMA_DECIMAL_DOMAINS = {
    "amazon.com.br",
    "amazon.de",
    "amazon.es",
    "amazon.fr",
    "amazon.it",
    "amazon.nl",
}


def _currency_for_url(source_url: str) -> str:
    host = (urlparse(source_url).hostname or "").lower()
    for domain, currency in DOMAIN_CURRENCIES.items():
        if host == domain or host.endswith(f".{domain}"):
            return currency
    return ""


def extract_amazon_asin(source_url: str) -> str | None:
    match = ASIN_PATTERN.search(urlparse(source_url).path)
    return match.group(1).upper() if match else None


def extract_snapshot_asins(html: str) -> set[str]:
    soup = BeautifulSoup(html, "html.parser")
    candidates: set[str] = set()
    asin_input = soup.select_one("#ASIN")
    if asin_input and asin_input.get("value"):
        candidates.add(str(asin_input["value"]).strip().upper())
    canonical = soup.select_one("link[rel='canonical']")
    if canonical and canonical.get("href"):
        canonical_asin = extract_amazon_asin(str(canonical["href"]))
        if canonical_asin:
            candidates.add(canonical_asin)
    return {candidate for candidate in candidates if re.fullmatch(r"[A-Z0-9]{10}", candidate)}


def extract_displayed_asin(html_or_soup: str | BeautifulSoup) -> str | None:
    soup = (
        html_or_soup
        if isinstance(html_or_soup, BeautifulSoup)
        else BeautifulSoup(html_or_soup, "html.parser")
    )
    asin_input = soup.select_one("#ASIN")
    asin = str(asin_input.get("value", "")).strip().upper() if asin_input else ""
    if re.fullmatch(r"[A-Z0-9]{10}", asin):
        return asin
    for script in soup.select("script"):
        script_text = script.string or script.get_text(" ", strip=False)
        match = re.search(
            r'''["'](?:winningAsin|currentAsin)["']\s*:\s*["']([A-Z0-9]{10})["']''',
            script_text,
            re.IGNORECASE,
        )
        if match:
            return match.group(1).upper()
    return None


def _normalize_number(value: str) -> float:
    compact = re.sub(r"\s", "", value)
    comma = compact.rfind(",")
    dot = compact.rfind(".")
    if comma >= 0 and dot >= 0:
        decimal = "," if comma > dot else "."
        grouping = "." if decimal == "," else ","
        compact = compact.replace(grouping, "").replace(decimal, ".")
    elif comma >= 0 or dot >= 0:
        separator = "," if comma >= 0 else "."
        parts = compact.split(separator)
        if len(parts[-1]) == 2:
            compact = "".join(parts[:-1]) + "." + parts[-1]
        else:
            compact = "".join(parts)
    return float(compact)


def _parse_price(value: str, source_url: str) -> dict:
    match = re.search(
        r"(?P<prefix>US\$|MX\$|CDN\$|CA\$|A\$|R\$|USD|MXN|CAD|AUD|BRL|GBP|EUR|JPY|[$€£¥￥])?"
        r"\s*(?P<number>\d[\d.,\s]*\d|\d)"
        r"\s*(?P<suffix>USD|MXN|CAD|AUD|BRL|GBP|EUR|JPY|[$€£¥￥])?",
        value,
        re.IGNORECASE,
    )
    if not match:
        return {"amount": None, "currency": ""}
    token = (match.group("prefix") or match.group("suffix") or "").upper()
    amount = _normalize_number(match.group("number"))
    currency = EXPLICIT_CURRENCIES.get(token, "")
    if token == "$" or not currency:
        currency = _currency_for_url(source_url)
    return {"amount": amount, "currency": currency}


def _valid_image_url(value: object) -> str:
    url = str(value or "").strip()
    return url if url.startswith(("https://", "http://")) else ""


def _append_unique(values: list[str], value: object) -> None:
    normalized = _valid_image_url(value)
    if normalized and normalized not in values:
        values.append(normalized)


def _extract_images(soup: BeautifulSoup) -> list[str]:
    images: list[str] = []
    landing = soup.select_one("#landingImage")
    if landing:
        _append_unique(images, landing.get("data-old-hires"))
        dynamic = landing.get("data-a-dynamic-image")
        if dynamic:
            try:
                for url in json.loads(str(dynamic)):
                    _append_unique(images, url)
            except (TypeError, ValueError):
                pass
        _append_unique(images, landing.get("src"))
    for image in soup.select("#altImages img, #imageBlock img"):
        _append_unique(images, image.get("data-old-hires"))
        _append_unique(images, image.get("data-src"))
        _append_unique(images, image.get("src"))
    return images


def _json_object_after_key(text: str, key: str) -> dict:
    match = re.search(rf'["\']{re.escape(key)}["\']\s*:\s*', text)
    if not match:
        return {}
    fragment = _balanced_object(text, match.end())
    if not fragment:
        return {}
    try:
        value = json.loads(fragment)
    except (TypeError, ValueError):
        try:
            value = ast.literal_eval(_pythonize_javascript_literals(fragment))
        except (SyntaxError, ValueError):
            return {}
    return value if isinstance(value, dict) else {}


def _balanced_object(text: str, start: int) -> str:
    while start < len(text) and text[start].isspace():
        start += 1
    if start >= len(text) or text[start] != "{":
        return ""
    depth = 0
    quote = ""
    escaped = False
    for index in range(start, len(text)):
        character = text[index]
        if quote:
            if escaped:
                escaped = False
            elif character == "\\":
                escaped = True
            elif character == quote:
                quote = ""
            continue
        if character in ("'", '"'):
            quote = character
        elif character == "{":
            depth += 1
        elif character == "}":
            depth -= 1
            if depth == 0:
                return text[start : index + 1]
    return ""


def _pythonize_javascript_literals(value: str) -> str:
    replacements = {"null": "None", "true": "True", "false": "False", "undefined": "None"}
    result: list[str] = []
    quote = ""
    escaped = False
    index = 0
    while index < len(value):
        character = value[index]
        if quote:
            result.append(character)
            if escaped:
                escaped = False
            elif character == "\\":
                escaped = True
            elif character == quote:
                quote = ""
            index += 1
            continue
        if character in ("'", '"'):
            quote = character
            result.append(character)
            index += 1
            continue
        replaced = False
        for token, replacement in replacements.items():
            if not value.startswith(token, index):
                continue
            before = value[index - 1] if index else ""
            after_index = index + len(token)
            after = value[after_index] if after_index < len(value) else ""
            if (not before or not (before.isalnum() or before == "_")) and (
                not after or not (after.isalnum() or after == "_")
            ):
                result.append(replacement)
                index = after_index
                replaced = True
                break
        if not replaced:
            result.append(character)
            index += 1
    return "".join(result).replace("\\/", "/")


def _gallery_entry_url(entry: object) -> str:
    if isinstance(entry, str):
        return _valid_image_url(entry)
    if not isinstance(entry, dict):
        return ""
    high_resolution = _valid_image_url(entry.get("hiRes"))
    if high_resolution:
        return high_resolution
    main = entry.get("main")
    if isinstance(main, dict):
        candidates: list[tuple[float, str]] = []
        for raw_url, raw_dimensions in main.items():
            image_url = _valid_image_url(raw_url)
            if not image_url:
                continue
            area = 0.0
            if isinstance(raw_dimensions, (list, tuple)) and len(raw_dimensions) >= 2:
                try:
                    area = float(raw_dimensions[0]) * float(raw_dimensions[1])
                except (TypeError, ValueError):
                    pass
            candidates.append((area, image_url))
        if candidates:
            return max(candidates, key=lambda candidate: candidate[0])[1]
    for field in ("large", "mainUrl", "landingUrl", "thumb"):
        value = _valid_image_url(entry.get(field))
        if value:
            return value
    return ""


def _extract_script_image_sets(
    soup: BeautifulSoup, selected_asin: str
) -> tuple[list[str], dict[str, list[str]], dict[str, str]]:
    selected_images: list[str] = []
    images_by_asin: dict[str, list[str]] = {}
    color_by_asin: dict[str, str] = {}
    for script in soup.select("script"):
        script_text = script.string or script.get_text(" ", strip=False)
        color_images = _json_object_after_key(script_text, "colorImages")
        if not color_images:
            continue
        color_to_asin = _json_object_after_key(script_text, "colorToAsin")
        asin_by_color: dict[str, str] = {}
        for color, raw_mapping in color_to_asin.items():
            candidate = raw_mapping.get("asin") if isinstance(raw_mapping, dict) else raw_mapping
            asin = str(candidate or "").strip().upper()
            if re.fullmatch(r"[A-Z0-9]{10}", asin):
                asin_by_color[str(color)] = asin

        for group_name, entries in color_images.items():
            if not isinstance(entries, list):
                continue
            asin = selected_asin if group_name == "initial" else asin_by_color.get(group_name, "")
            if not asin:
                continue
            asin_images = images_by_asin.setdefault(asin, [])
            for entry in entries:
                image_url = _gallery_entry_url(entry)
                _append_unique(asin_images, image_url)
                if group_name == "initial" or asin == selected_asin:
                    _append_unique(selected_images, image_url)
            if group_name != "initial":
                color_by_asin.setdefault(asin, str(group_name).strip())
    return selected_images, images_by_asin, color_by_asin


def _variant_label(group_id: str) -> str:
    raw = group_id.removeprefix("variation_").removesuffix("_name")
    return raw.replace("_", " ").strip().title()


def _variant_value(option) -> str:
    candidates = [
        option.get("title"),
        option.select_one("img").get("alt") if option.select_one("img") else "",
        _text(option.select_one(".a-button-text")),
        _text(option),
    ]
    for candidate in candidates:
        value = str(candidate or "").strip()
        if not value:
            continue
        value = re.sub(r"^click to select\s+", "", value, flags=re.IGNORECASE)
        value = re.sub(r"^select\s+", "", value, flags=re.IGNORECASE)
        if value:
            return value
    return ""


def _extract_variants(
    soup: BeautifulSoup,
    source_url: str,
    selected_asin: str | None = None,
    script_images_by_asin: dict[str, list[str]] | None = None,
    script_color_by_asin: dict[str, str] | None = None,
) -> list[dict]:
    variants: dict[str, dict] = {}
    for group in soup.select("[id^='variation_'][id$='_name']"):
        attribute = _variant_label(str(group.get("id", "")))
        if not attribute:
            continue
        for option in group.select("[data-asin]"):
            asin = str(option.get("data-asin", "")).strip().upper()
            if not re.fullmatch(r"[A-Z0-9]{10}", asin):
                continue
            variant = variants.setdefault(
                asin,
                {"asin": asin, "attributes": {}, "image_urls": [], "selected": False},
            )
            value = _variant_value(option)
            if value:
                variant["attributes"][attribute] = value
            image = option.select_one("img")
            if image:
                _append_unique(variant["image_urls"], image.get("data-old-hires"))
                _append_unique(variant["image_urls"], image.get("src"))
            classes = {str(item).lower() for item in option.get("class", [])}
            if "selected" in classes or str(option.get("aria-checked", "")).lower() == "true":
                variant["selected"] = True

    for script in soup.select("script"):
        text = script.string or script.get_text(" ", strip=False)
        display_data = _json_object_after_key(text, "dimensionValuesDisplayData")
        if not display_data:
            continue
        variation_values = _json_object_after_key(text, "variationValues")
        attributes = [_variant_label(f"variation_{name}") for name in variation_values]
        for asin, values in display_data.items():
            normalized_asin = str(asin).strip().upper()
            if not re.fullmatch(r"[A-Z0-9]{10}", normalized_asin):
                continue
            if not isinstance(values, list):
                continue
            variant = variants.setdefault(
                normalized_asin,
                {
                    "asin": normalized_asin,
                    "attributes": {},
                    "image_urls": [],
                    "selected": False,
                },
            )
            for attribute, value in zip(attributes, values, strict=False):
                if attribute and str(value).strip():
                    variant["attributes"].setdefault(attribute, str(value).strip())

    for asin, image_urls in (script_images_by_asin or {}).items():
        variant = variants.setdefault(
            asin,
            {"asin": asin, "attributes": {}, "image_urls": [], "selected": False},
        )
        if image_urls:
            variant["image_urls"] = list(image_urls)
        color = (script_color_by_asin or {}).get(asin, "")
        if color:
            variant["attributes"].setdefault("Color", color)

    selected_asin = selected_asin or extract_amazon_asin(source_url) or ""
    for asin, variant in variants.items():
        variant["selected"] = bool(selected_asin and asin == selected_asin)
    return sorted(variants.values(), key=lambda item: (not item["selected"], item["asin"]))


def _parse_weight(raw: str, decimal_separator: str = ".") -> dict | None:
    match = re.search(
        r"(?P<value>\d+(?:[.,]\d+)?)\s*(?P<unit>lb|lbs|pounds?|oz|ounces?|kg|kilograms?|g|grams?)\b",
        raw,
        re.IGNORECASE,
    )
    if not match:
        return None
    unit = WEIGHT_UNITS.get(match.group("unit").lower())
    if not unit:
        return None
    return {
        "value": _parse_measurement_number(match.group("value"), decimal_separator),
        "unit": unit,
        "raw": raw,
    }


def _parse_dimensions(raw: str, decimal_separator: str = ".") -> dict | None:
    match = re.search(
        r"(?P<length>\d+(?:[.,]\d+)?)\s*[x×]\s*"
        r"(?P<width>\d+(?:[.,]\d+)?)\s*[x×]\s*"
        r"(?P<height>\d+(?:[.,]\d+)?)\s*"
        r"(?P<unit>inches?|in|centimeters?|cm|millimeters?|mm|feet|foot|ft|meters?|m)\b",
        raw,
        re.IGNORECASE,
    )
    if not match:
        return None
    unit = DIMENSION_UNITS.get(match.group("unit").lower())
    if not unit:
        return None
    return {
        "length": _parse_measurement_number(match.group("length"), decimal_separator),
        "width": _parse_measurement_number(match.group("width"), decimal_separator),
        "height": _parse_measurement_number(match.group("height"), decimal_separator),
        "unit": unit,
        "raw": raw,
    }


def _parse_measurement_number(value: str, decimal_separator: str) -> float:
    compact = value.replace(" ", "")
    if "," in compact and "." in compact:
        return _normalize_number(compact)
    separator = "," if "," in compact else "." if "." in compact else ""
    if not separator:
        return float(compact)
    parts = compact.split(separator)
    if separator != decimal_separator:
        return float("".join(parts))
    if len(parts) == 2:
        return float(f"{parts[0]}.{parts[1]}")
    return float("".join(parts))


def _extract_measurements(
    technical_details: dict[str, str], source_url: str
) -> dict[str, dict]:
    measurements: dict[str, dict] = {}
    host = (urlparse(source_url).hostname or "").lower()
    decimal_separator = "," if any(
        host == domain or host.endswith(f".{domain}") for domain in COMMA_DECIMAL_DOMAINS
    ) else "."
    aliases = {
        "itemweight": ("item_weight", _parse_weight),
        "productweight": ("item_weight", _parse_weight),
        "packageweight": ("package_weight", _parse_weight),
        "shippingweight": ("package_weight", _parse_weight),
        "productdimensions": ("product_dimensions", _parse_dimensions),
        "itemdimensionslxwxh": ("product_dimensions", _parse_dimensions),
        "packagedimensions": ("package_dimensions", _parse_dimensions),
    }
    for label, raw in technical_details.items():
        normalized_label = re.sub(r"[^a-z0-9]", "", label.lower())
        target = aliases.get(normalized_label)
        if not target:
            continue
        field, parser = target
        parsed = parser(raw, decimal_separator)
        if parsed and field not in measurements:
            measurements[field] = {**parsed, "source_label": label}
    return measurements


def parse_amazon_html(html: str, source_url: str) -> dict:
    soup = BeautifulSoup(html, "html.parser")
    title = _text(soup.select_one("#productTitle"))
    price_node = soup.select_one(
        "#corePrice_feature_div .a-offscreen, .a-price .a-offscreen, "
        "#priceblock_ourprice, #priceblock_dealprice"
    )
    price = _parse_price(_text(price_node), source_url)
    byline = _text(soup.select_one("#bylineInfo"))
    brand = byline.replace("Brand:", "").replace("Visit the", "").replace("Store", "").strip()
    bullets = [_text(item) for item in soup.select("#feature-bullets li") if _text(item)]
    description = _text(soup.select_one("#productDescription"))
    selected_asin = extract_displayed_asin(soup) or extract_amazon_asin(source_url) or ""
    script_images, script_images_by_asin, script_color_by_asin = _extract_script_image_sets(
        soup, selected_asin
    )
    images = list(script_images)
    for image_url in _extract_images(soup):
        _append_unique(images, image_url)
    technical_details = {}
    for row in soup.select(
        "#productDetails_techSpec_section_1 tr, #productDetails_detailBullets_sections1 tr, "
        "#productOverview_feature_div tr"
    ):
        key = _text(row.select_one("th"))
        cells = row.select("td")
        value = _text(cells[0]) if key and cells else ""
        if not key and len(cells) >= 2:
            key = _text(cells[0])
            value = _text(cells[1])
        if key and value:
            technical_details[key] = value
    for item in soup.select("#detailBullets_feature_div li"):
        key_node = item.select_one(".a-text-bold")
        key_text = _text(key_node).replace("\u200e", "")
        key = key_text.rstrip(": ")
        full_value = _text(item)
        value = full_value.replace("\u200e", "")[len(key_text) :].strip(" :") if key_node else ""
        if key and value:
            technical_details.setdefault(key, value)
    return {
        "source_url": source_url,
        "title": title,
        "price": price,
        "brand": brand,
        "bullets": bullets,
        "description": description,
        "images": images,
        "variants": _extract_variants(
            soup,
            source_url,
            selected_asin=selected_asin,
            script_images_by_asin=script_images_by_asin,
            script_color_by_asin=script_color_by_asin,
        ),
        "technical_details": technical_details,
        "measurements": _extract_measurements(technical_details, source_url),
    }
