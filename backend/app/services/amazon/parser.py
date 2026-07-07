import re

from bs4 import BeautifulSoup


def _text(node) -> str:
    return " ".join(node.get_text(" ", strip=True).split()) if node else ""


def _parse_price(value: str) -> dict:
    match = re.search(r"([A-Z$]*)([0-9]+(?:[.,][0-9]{2})?)", value)
    if not match:
        return {"amount": None, "currency": ""}
    symbol = match.group(1)
    amount = float(match.group(2).replace(",", "."))
    currency = "USD" if "$" in symbol or symbol == "" else symbol
    return {"amount": amount, "currency": currency}


def parse_amazon_html(html: str, source_url: str) -> dict:
    soup = BeautifulSoup(html, "html.parser")
    title = _text(soup.select_one("#productTitle"))
    price = _parse_price(_text(soup.select_one(".a-price .a-offscreen")))
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
