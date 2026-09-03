import pytest

from app.services.amazon.collector import validate_amazon_snapshot
from app.services.amazon.media import (
    merge_listing_images,
    prepare_listing_title,
    select_listing_images,
    select_product_video_urls,
)
from app.services.amazon.normalizer import normalize_amazon_product
from app.services.amazon.parser import _normalize_measurement_label, parse_amazon_html


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


def test_parse_amazon_html_ignores_recommendation_price_outside_product_area():
    html = """
    <span id="productTitle">Unavailable product</span>
    <div id="recommendations">
      <span class="a-price"><span class="a-offscreen">$17.77</span></span>
    </div>
    """

    parsed = parse_amazon_html(html, "https://www.amazon.com/dp/B000TEST01")

    assert parsed["title"] == "Unavailable product"
    assert parsed["price"] == {"amount": None, "currency": ""}


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


@pytest.mark.parametrize(
    (
        "source_url",
        "weight_label",
        "weight",
        "dimension_label",
        "dimensions",
        "field",
        "expected_weight",
        "expected_weight_unit",
        "expected_length",
    ),
    [
        (
            "https://amazon.es/dp/B000TEST01",
            "Peso del producto",
            "1,5 kilogramos",
            "Dimensiones del producto",
            "30 x 20 x 10 centímetros",
            "item_weight",
            1.5,
            "kg",
            30.0,
        ),
        (
            "https://amazon.com.br/dp/B000TEST01",
            "Peso da embalagem",
            "750 gramas",
            "Dimensões da embalagem",
            "40 x 30 x 20 centímetros",
            "package_weight",
            750.0,
            "g",
            40.0,
        ),
        (
            "https://amazon.de/dp/B000TEST01",
            "Artikelgewicht",
            "1,25 Pfund",
            "Produktabmessungen",
            "12,5 x 8,5 x 4,5 Zentimeter",
            "item_weight",
            1.25,
            "lb",
            12.5,
        ),
        (
            "https://amazon.fr/dp/B000TEST01",
            "Poids du colis",
            "2,5 kilogrammes",
            "Dimensions du colis",
            "35 x 25 x 15 centimètres",
            "package_weight",
            2.5,
            "kg",
            35.0,
        ),
        (
            "https://amazon.it/dp/B000TEST01",
            "Peso articolo",
            "500 grammi",
            "Dimensioni del prodotto",
            "28 x 18 x 8 centimetri",
            "item_weight",
            500.0,
            "g",
            28.0,
        ),
        (
            "https://amazon.nl/dp/B000TEST01",
            "Productgewicht",
            "600 gram",
            "Productafmetingen",
            "25 x 15 x 5 centimeter",
            "item_weight",
            600.0,
            "g",
            25.0,
        ),
        (
            "https://amazon.co.jp/dp/B000TEST01",
            "商品の重量",
            "500 グラム",
            "製品サイズ",
            "30 x 20 x 10 センチメートル",
            "item_weight",
            500.0,
            "g",
            30.0,
        ),
    ],
)
def test_parse_amazon_localized_measurements(
    source_url: str,
    weight_label: str,
    weight: str,
    dimension_label: str,
    dimensions: str,
    field: str,
    expected_weight: float,
    expected_weight_unit: str,
    expected_length: float,
):
    html = f"""
    <span id="productTitle">Localized details</span>
    <table id="productDetails_techSpec_section_1">
      <tr><th>{weight_label}</th><td>{weight}</td></tr>
      <tr><th>{dimension_label}</th><td>{dimensions}</td></tr>
    </table>
    """

    parsed = parse_amazon_html(html, source_url)
    dimension_field = "package_dimensions" if field == "package_weight" else "product_dimensions"

    parsed_weight = parsed["measurements"][field]
    parsed_dimensions = parsed["measurements"][dimension_field]

    assert parsed_weight["source_label"] == weight_label
    assert parsed_weight["value"] == expected_weight
    assert parsed_weight["unit"] == expected_weight_unit
    assert parsed_dimensions["source_label"] == dimension_label
    assert parsed_dimensions["length"] == expected_length
    assert parsed_dimensions["unit"] == "cm"


def test_measurement_label_normalization_preserves_non_latin_case():
    assert _normalize_measurement_label("Σ 商品") == "Σ商品"
    assert _normalize_measurement_label("DIMENSÕES DO PRODUTO") == "dimensoesdoproduto"


def test_normalize_amazon_product_creates_draft_defaults():
    parsed = parse_amazon_html(HTML, "https://www.amazon.com/dp/B000TEST01")
    draft = normalize_amazon_product(parsed, target_site_id="MLM")
    assert draft.title == "Stainless Water Bottle"
    assert draft.target_site_id == "MLM"
    assert draft.source_price == 19.99
    assert draft.source_currency == "USD"
    assert draft.price is None
    assert draft.currency == "MXN"
    assert draft.stock == 0
    assert draft.condition == ""


def test_normalize_amazon_product_removes_source_brand_and_gallery_sizes():
    parsed = {
        "title": "CAKETIME Silicone Muffin Pan, Best Sale",
        "brand": "CAKETIME",
        "description": "",
        "bullets": ["CAKETIME silicone pan"],
        "technical_details": {},
        "images": [
            "https://m.media-amazon.com/images/I/hero._AC_SL1500_.jpg",
            "https://m.media-amazon.com/images/I/hero._AC_SY450_.jpg",
            "https://m.media-amazon.com/images/I/side._AC_SL1200_.jpg",
            "https://m.media-amazon.com/images/I/side._AC_US100_.jpg",
        ],
        "price": {"amount": 10, "currency": "USD"},
    }

    draft = normalize_amazon_product(parsed, target_site_id="MLM")

    assert draft.title == "Silicone Muffin Pan"
    assert "CAKETIME" not in draft.description
    assert draft.image_urls == [
        "https://m.media-amazon.com/images/I/hero._AC_SL1500_.jpg",
        "https://m.media-amazon.com/images/I/side._AC_SL1200_.jpg",
    ]


def test_select_listing_images_keeps_eligible_gallery_order_after_deduplication():
    images = [
        "https://example.com/a._AC_US100_.jpg",
        "https://example.com/b._AC_SL1200_.jpg",
        "https://example.com/a._AC_SY450_.jpg",
        "https://example.com/b._AC_SX500_.jpg",
    ]

    assert select_listing_images(images, limit=1) == ["https://example.com/a._AC_SY450_.jpg"]
    assert prepare_listing_title("CAKETIME Best Silicone Pan", "CAKETIME") == "Silicone Pan"


def test_select_listing_images_deduplicates_unprefixed_amazon_responsive_gallery_urls():
    images = [
        "https://m.media-amazon.com/images/I/71Plkrjg7vL._SL1500_.jpg",
        "https://m.media-amazon.com/images/I/71Plkrjg7vL._SX342_.jpg",
        "https://m.media-amazon.com/images/I/71Plkrjg7vL._SX385_.jpg",
        "https://m.media-amazon.com/images/I/71Plkrjg7vL._SX466_.jpg",
        "https://m.media-amazon.com/images/I/41DFwtawoGL._SX38_SY50_CR,0,0,38,50_.jpg",
    ]

    assert select_listing_images(images) == [
        "https://m.media-amazon.com/images/I/71Plkrjg7vL._SL1500_.jpg",
    ]


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


def test_parse_amazon_json5_script_gallery_and_variant_dimensions():
    html = """
    <input id="ASIN" value="B000TEST01" />
    <span id="productTitle">JSON5 variant bottle</span>
    <script>
      // colorImages: {}
      // dimensionValuesDisplayData: {}
      var imageData = {
        // Some Amazon page variants emit JavaScript objects { rather than JSON }.
        colorImages: /* the object's gallery */ {
          initial: [{hiRes: 'https://example.com/black-main.jpg',},],
          Blue: [{mainUrl: 'https://example.com/blue-main.jpg',},],
        },
        colorToAsin: {
          /* Don't alter undefined here; ignore structural tokens: { } */
          Blue: {asin: 'B000TEST02',},
        },
        variationValues: {
          color_name: ['Black', 'Blue'],
          size_name: ['20 oz', '32 oz'],
        },
        dimensionValuesDisplayData: {
          B000TEST01: ['Black', '20 oz'],
          B000TEST02: ['Blue', '32 oz'],
          B000TEST03: [undefined, null],
        },
        unused: undefined,
      };
    </script>
    """

    parsed = parse_amazon_html(html, "https://amazon.com/dp/B000TEST01")

    assert parsed["images"] == ["https://example.com/black-main.jpg"]
    variants = {variant["asin"]: variant for variant in parsed["variants"]}
    assert variants["B000TEST01"] | {
        "attributes": {"Color": "Black", "Size": "20 oz"},
        "selected": True,
    } == variants["B000TEST01"]
    assert variants["B000TEST02"] == {
        "asin": "B000TEST02",
        "attributes": {"Color": "Blue", "Size": "32 oz"},
        "image_urls": ["https://example.com/blue-main.jpg"],
        "selected": False,
    }
    assert variants["B000TEST03"]["attributes"] == {}


def test_parse_amazon_measurements_from_second_technical_section():
    html = """
    <span id="productTitle">Second details table</span>
    <table id="productDetails_techSpec_section_2">
      <tr><th>Package Weight</th><td>2.5 kg</td></tr>
      <tr><th>Package Dimensions</th><td>40 x 30 x 20 cm</td></tr>
    </table>
    """

    parsed = parse_amazon_html(html, "https://amazon.com/dp/B000TEST01")

    assert parsed["measurements"]["package_weight"]["value"] == 2.5
    assert parsed["measurements"]["package_weight"]["unit"] == "kg"
    assert parsed["measurements"]["package_dimensions"] | {
        "length": 40.0,
        "width": 30.0,
        "height": 20.0,
        "unit": "cm",
    } == parsed["measurements"]["package_dimensions"]


def test_parse_amazon_dimensions_with_inline_weight_uses_explicit_weight_first():
    html = """
    <span id="productTitle">Composite measurements</span>
    <table id="productDetails_techSpec_section_1">
      <tr><th>Product Dimensions</th><td>12 x 8 x 4 inches; 1.5 Pounds</td></tr>
      <tr><th>Package Dimensions</th><td>14 x 10 x 6 inches; 2.25 Pounds</td></tr>
      <tr><th>Item Weight</th><td>1.25 Pounds</td></tr>
    </table>
    """

    parsed = parse_amazon_html(html, "https://amazon.com/dp/B000TEST01")

    assert parsed["measurements"]["product_dimensions"]["length"] == 12.0
    assert parsed["measurements"]["package_dimensions"]["length"] == 14.0
    assert parsed["measurements"]["item_weight"] == {
        "value": 1.25,
        "unit": "lb",
        "raw": "1.25 Pounds",
        "source_label": "Item Weight",
    }
    assert parsed["measurements"]["package_weight"] == {
        "value": 2.25,
        "unit": "lb",
        "raw": "14 x 10 x 6 inches; 2.25 Pounds",
        "source_label": "Package Dimensions",
    }


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


def test_select_product_video_urls_rejects_non_vse_or_non_amazon_urls():
    valid = "https://m.media-amazon.com/images/S/vse-vms-transcoding-artifact-us-east-1-prod/a/video.mp4"
    assert select_product_video_urls([
        "https://m.media-amazon.com/images/S/ads/recommendation.mp4",
        "https://cdn.example/video.mp4",
        valid,
        valid,
    ]) == [valid]


def test_select_listing_images_keeps_resizable_100px_render_and_rejects_tinier_icon():
    assert select_listing_images([
        "https://example.com/icon._AC_US99_.jpg",
        "https://example.com/eligible._AC_US100_.jpg",
    ]) == ["https://example.com/eligible._AC_US100_.jpg"]


def test_merge_listing_images_keeps_variant_and_shared_gallery_images():
    assert merge_listing_images(
        ["https://m.media-amazon.com/images/I/variant._SX500_.jpg"],
        [
            "https://m.media-amazon.com/images/I/shared-one._SL1200_.jpg",
            "https://m.media-amazon.com/images/I/shared-two._SL1200_.jpg",
        ],
    ) == [
        "https://m.media-amazon.com/images/I/variant._SX500_.jpg",
        "https://m.media-amazon.com/images/I/shared-one._SL1200_.jpg",
        "https://m.media-amazon.com/images/I/shared-two._SL1200_.jpg",
    ]
