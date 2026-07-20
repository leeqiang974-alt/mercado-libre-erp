from app.services.amazon.normalizer import normalize_amazon_product
from app.services.amazon.parser import parse_amazon_html


HTML = """
<html>
  <span id="productTitle">  Stainless Water Bottle  </span>
  <span class="a-price"><span class="a-offscreen">$19.99</span></span>
  <div id="bylineInfo">Brand: TrailPro</div>
  <div id="feature-bullets"><ul><li>Leak proof lid</li><li>24 oz capacity</li></ul></div>
  <div id="productDescription"><p>Keeps drinks cold.</p></div>
  <img id="landingImage" src="https://example.com/main.jpg" />
  <table id="productDetails_techSpec_section_1">
    <tr><th>Item Weight</th><td>1.2 pounds</td></tr>
  </table>
</html>
"""


def test_parse_amazon_html_extracts_core_fields():
    parsed = parse_amazon_html(HTML, "https://www.amazon.com/dp/B000TEST01")
    assert parsed["title"] == "Stainless Water Bottle"
    assert parsed["price"]["amount"] == 19.99
    assert parsed["brand"] == "TrailPro"
    assert parsed["images"] == ["https://example.com/main.jpg"]
    assert "Leak proof lid" in parsed["bullets"]
    assert parsed["technical_details"]["Item Weight"] == "1.2 pounds"


def test_normalize_amazon_product_creates_draft_defaults():
    parsed = parse_amazon_html(HTML, "https://www.amazon.com/dp/B000TEST01")
    draft = normalize_amazon_product(parsed, target_site_id="MLM")
    assert draft.title == "Stainless Water Bottle"
    assert draft.target_site_id == "MLM"
    assert draft.source_price == 19.99
    assert draft.source_currency == "USD"
    assert draft.price is None
    assert draft.currency == "MXN"
    assert draft.stock == 1


def test_parse_amazon_price_handles_grouping_and_site_currency():
    cases = [
        ("$1,299.99", "https://amazon.com/dp/A", 1299.99, "USD"),
        ("US$ 1,299.99", "https://amazon.com/dp/A", 1299.99, "USD"),
        ("MX$1,299.00", "https://amazon.com.mx/dp/A", 1299.0, "MXN"),
        ("1.299,99 €", "https://amazon.de/dp/A", 1299.99, "EUR"),
        ("￥12,980", "https://amazon.co.jp/dp/A", 12980.0, "JPY"),
        ("$49.90", "https://amazon.ca/dp/A", 49.9, "CAD"),
    ]
    for display, url, amount, currency in cases:
        html = f'<span id="productTitle">Item</span><span class="a-price"><span class="a-offscreen">{display}</span></span>'
        parsed = parse_amazon_html(html, url)
        assert parsed["price"] == {"amount": amount, "currency": currency}
