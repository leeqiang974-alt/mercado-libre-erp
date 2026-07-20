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
    try:
        value, _ = json.JSONDecoder().raw_decode(text[match.end() :])
    except (TypeError, ValueError):
        return {}
    return value if isinstance(value, dict) else {}


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


def _extract_variants(soup: BeautifulSoup, source_url: str) -> list[dict]:
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

    selected_asin = extract_amazon_asin(source_url) or ""
    for asin, variant in variants.items():
        variant["selected"] = bool(selected_asin and asin == selected_asin)
    return sorted(variants.values(), key=lambda item: (not item["selected"], item["asin"]))


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
    images = _extract_images(soup)
    technical_details = {}
    for row in soup.select("#productDetails_techSpec_section_1 tr, #productDetails_detailBullets_sections1 tr"):
        key = _text(row.select_one("th"))
        value = _text(row.select_one("td"))
        if key and value:
            technical_details[key] = value
    return {
        "source_url": source_url,
        "title": title,
        "price": price,
        "brand": brand,
        "bullets": bullets,
        "description": description,
        "images": images,
        "variants": _extract_variants(soup, source_url),
        "technical_details": technical_details,
    }
