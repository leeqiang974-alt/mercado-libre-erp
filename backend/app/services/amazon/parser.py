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
}

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


def parse_amazon_html(html: str, source_url: str) -> dict:
    soup = BeautifulSoup(html, "html.parser")
    title = _text(soup.select_one("#productTitle"))
    price = _parse_price(_text(soup.select_one(".a-price .a-offscreen")), source_url)
    byline = _text(soup.select_one("#bylineInfo"))
    brand = byline.replace("Brand:", "").replace("Visit the", "").replace("Store", "").strip()
    bullets = [_text(item) for item in soup.select("#feature-bullets li") if _text(item)]
    description = _text(soup.select_one("#productDescription"))
    images = []
    landing = soup.select_one("#landingImage")
    if landing and landing.get("src"):
        images.append(landing["src"])
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
        "technical_details": technical_details,
    }
