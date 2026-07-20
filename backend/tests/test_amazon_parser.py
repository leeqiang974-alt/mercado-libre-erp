import pytest

from app.services.amazon.collector import validate_amazon_snapshot
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
    <tr><th>Product Dimensions</th><td>12 x 8 x 4 inches</td></tr>
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
    assert parsed["measurements"] == {
        "item_weight": {
            "value": 1.2,
            "unit": "lb",
            "raw": "1.2 pounds",
            "source_label": "Item Weight",
        },
        "product_dimensions": {
            "length": 12.0,
            "width": 8.0,
            "height": 4.0,
            "unit": "in",
            "raw": "12 x 8 x 4 inches",
            "source_label": "Product Dimensions",
        },
    }


def test_parse_amazon_detail_bullets_extracts_package_measurements():
    html = """
    <span id="productTitle">Package evidence</span>
    <div id="detailBullets_feature_div"><ul>
      <li><span><span class="a-text-bold">Package Dimensions :</span> 30 × 20 × 10 cm</span></li>
      <li><span><span class="a-text-bold">Shipping Weight :</span> 750 grams</span></li>
    </ul></div>
    """

    parsed = parse_amazon_html(html, "https://amazon.com/dp/B000TEST01")

    assert parsed["measurements"]["package_dimensions"]["unit"] == "cm"
    assert parsed["measurements"]["package_dimensions"]["length"] == 30
    assert parsed["measurements"]["package_weight"] == {
        "value": 750.0,
        "unit": "g",
        "raw": "750 grams",
        "source_label": "Shipping Weight",
    }


def test_parse_amazon_measurements_handles_grouping_and_overview_cells():
    html = """
    <span id="productTitle">Localized measurements</span>
    <div id="productOverview_feature_div"><table>
      <tr><td>Item Weight</td><td>1.200 grams</td></tr>
      <tr><td>Product Dimensions</td><td>12,5 x 8,5 x 4,5 cm</td></tr>
    </table></div>
    """

    parsed = parse_amazon_html(html, "https://amazon.de/dp/B000TEST01")

    assert parsed["measurements"]["item_weight"]["value"] == 1200
    assert parsed["measurements"]["product_dimensions"] | {
        "length": 12.5,
        "width": 8.5,
        "height": 4.5,
    } == parsed["measurements"]["product_dimensions"]


def test_parse_amazon_measurements_preserves_three_decimal_values():
    html = """
    <span id="productTitle">Precise measurements</span>
    <table id="productDetails_techSpec_section_1">
      <tr><th>Item Weight</th><td>0.125 pounds</td></tr>
      <tr><th>Product Dimensions</th><td>1.125 x 0.125 x 0.250 inches</td></tr>
    </table>
    """

    parsed = parse_amazon_html(html, "https://amazon.com/dp/B000TEST01")

    assert parsed["measurements"]["item_weight"]["value"] == 0.125
    assert parsed["measurements"]["product_dimensions"] | {
        "length": 1.125,
        "width": 0.125,
        "height": 0.25,
    } == parsed["measurements"]["product_dimensions"]


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


def test_parse_amazon_html_extracts_image_gallery_and_variants():
    html = """
    <input id="ASIN" value="B000TEST01" />
    <span id="productTitle">Variant Bottle</span>
    <span class="a-price"><span class="a-offscreen">$24.99</span></span>
    <img id="landingImage"
         src="https://example.com/fallback.jpg"
         data-old-hires="https://example.com/hero.jpg"
         data-a-dynamic-image='{"https://example.com/hero.jpg":[1200,1200],"https://example.com/side.jpg":[1000,1000]}' />
    <div id="altImages"><img src="https://example.com/detail.jpg" /></div>
    <div id="variation_color_name">
      <ul>
        <li class="selected" data-asin="B000TEST01" title="Click to select Black">
          <img alt="Black" src="https://example.com/black.jpg" />
        </li>
        <li data-asin="B000TEST02" title="Click to select Blue">
          <img alt="Blue" src="https://example.com/blue.jpg" />
        </li>
      </ul>
    </div>
    <script>
      var data = {
        "variationValues":{"color_name":["Black","Blue"],"size_name":["20 oz","32 oz"]},
        "dimensionValuesDisplayData":{"B000TEST01":["Black","20 oz"],"B000TEST03":["Blue","32 oz"]}
      };
    </script>
    """

    parsed = parse_amazon_html(html, "https://www.amazon.com/dp/B000TEST01")

    assert parsed["images"] == [
        "https://example.com/hero.jpg",
        "https://example.com/side.jpg",
        "https://example.com/fallback.jpg",
        "https://example.com/detail.jpg",
    ]
    variants = {variant["asin"]: variant for variant in parsed["variants"]}
    assert variants["B000TEST01"]["selected"] is True
    assert variants["B000TEST01"]["attributes"] == {
        "Color": "Black",
        "Size": "20 oz",
    }
    assert variants["B000TEST02"]["attributes"] == {"Color": "Blue"}
    assert variants["B000TEST03"]["attributes"] == {
        "Color": "Blue",
        "Size": "32 oz",
    }
    assert variants["B000TEST02"]["image_urls"] == ["https://example.com/blue.jpg"]


def test_parse_amazon_script_gallery_binds_high_resolution_images_to_asins():
    html = """
    <input id="ASIN" value="B000TEST01" />
    <span id="productTitle">Script gallery bottle</span>
    <img id="landingImage" src="https://example.com/landing-thumb.jpg" />
    <div id="variation_color_name">
      <span data-asin="B000TEST02" title="Blue">
        <img src="https://example.com/blue-swatch-thumb.jpg" />
      </span>
    </div>
    <script>
      var imageData = {
        'colorImages': {
          'initial': [
            {'hiRes':'https://example.com/black-main-hires.jpg','large':'https://example.com/black-main-large.jpg'},
            {'hiRes':null,'large':'https://example.com/black-side-large.jpg'}
          ],
          'Black': [
            {'large':'https://example.com/black-main-hires.jpg'},
            {'mainUrl':'https://example.com/black-detail.jpg'}
          ],
          'Blue': [
            {'hiRes':'https://example.com/blue-main-hires.jpg'},
            {
              'hiRes':null,
              'large':'https://example.com/blue-side-large.jpg',
              'main': {
                'https://example.com/blue-side-small.jpg':[400,400],
                'https://example.com/blue-side-max.jpg':[1600,1200]
              }
            }
          ]
        },
        'colorToAsin': {
          'Black':{'asin':'B000TEST01'},
          'Blue':{'asin':'B000TEST02'}
        }
      };
    </script>
    """

    parsed = parse_amazon_html(html, "https://www.amazon.com/dp/B000TEST01")

    assert parsed["images"] == [
        "https://example.com/black-main-hires.jpg",
        "https://example.com/black-side-large.jpg",
        "https://example.com/black-detail.jpg",
        "https://example.com/landing-thumb.jpg",
    ]
    variants = {variant["asin"]: variant for variant in parsed["variants"]}
    assert variants["B000TEST01"]["selected"] is True
    assert variants["B000TEST01"]["attributes"] == {"Color": "Black"}
    assert variants["B000TEST01"]["image_urls"] == [
        "https://example.com/black-main-hires.jpg",
        "https://example.com/black-side-large.jpg",
        "https://example.com/black-detail.jpg",
    ]
    assert variants["B000TEST02"]["selected"] is False
    assert variants["B000TEST02"]["attributes"] == {"Color": "Blue"}
    assert variants["B000TEST02"]["image_urls"] == [
        "https://example.com/blue-main-hires.jpg",
        "https://example.com/blue-side-max.jpg",
    ]


def test_displayed_asin_owns_initial_gallery_and_mismatch_is_rejected():
    html = """
    <link rel="canonical" href="https://amazon.com/dp/B000TEST01" />
    <span id="productTitle">Redirected Bottle</span>
    <span class="a-price"><span class="a-offscreen">$20.00</span></span>
    <script>
      var imageData = {
        'winningAsin':'B000TEST02',
        'colorImages': {'initial':[{'hiRes':'https://example.com/blue.jpg'}]},
        'colorToAsin': {}
      };
    </script>
    """

    parsed = parse_amazon_html(html, "https://amazon.com/dp/B000TEST01")

    variants = {variant["asin"]: variant for variant in parsed["variants"]}
    assert variants["B000TEST02"]["selected"] is True
    assert variants["B000TEST02"]["image_urls"] == ["https://example.com/blue.jpg"]
    assert "B000TEST01" not in variants
    with pytest.raises(ValueError, match="amazon_snapshot_identity_mismatch"):
        validate_amazon_snapshot("https://amazon.com/dp/B000TEST01", html)


def test_requested_url_asin_wins_when_snapshot_contains_another_canonical_asin():
    html = """
    <input id="ASIN" value="B000TEST01" />
    <link rel="canonical" href="https://amazon.com/dp/B000TEST02" />
    <span id="productTitle">Conflicting identity</span>
    <div id="variation_color_name">
      <span data-asin="B000TEST01" title="Black"></span>
      <span class="selected" data-asin="B000TEST02" title="Blue"></span>
    </div>
    """

    parsed = parse_amazon_html(html, "https://amazon.com/dp/B000TEST01")

    variants = {variant["asin"]: variant for variant in parsed["variants"]}
    assert variants["B000TEST01"]["selected"] is True
    assert variants["B000TEST02"]["selected"] is False


def test_no_other_variant_is_selected_when_requested_asin_is_not_in_options():
    html = """
    <input id="ASIN" value="B000TEST01" />
    <span id="productTitle">Missing current option</span>
    <div id="variation_color_name">
      <span class="selected" data-asin="B000TEST02" title="Blue"></span>
    </div>
    """

    parsed = parse_amazon_html(html, "https://amazon.com/dp/B000TEST01")

    assert parsed["variants"][0]["asin"] == "B000TEST02"
    assert parsed["variants"][0]["selected"] is False
