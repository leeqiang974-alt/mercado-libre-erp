from app.services.amazon.discovery import build_amazon_search_url, extract_amazon_search_product_urls


def test_search_urls_are_converted_to_exact_product_urls():
    html = '''
    <div data-component-type="s-search-result" data-asin="B000TEST01"></div>
    <div data-component-type="s-search-result" data-asin="B000TEST02"></div>
    <div data-component-type="s-search-result" data-asin="B000TEST01"></div>
    '''
    search_url = build_amazon_search_url("www.amazon.com", "silicone mold")

    assert search_url == "https://www.amazon.com/s?k=silicone+mold"
    assert extract_amazon_search_product_urls(html, search_url, 20) == [
        "https://amazon.com/dp/B000TEST01",
        "https://amazon.com/dp/B000TEST02",
    ]


def test_discovery_rejects_non_amazon_domains():
    try:
        build_amazon_search_url("example.com", "bottle")
    except ValueError as exc:
        assert str(exc) == "only_public_amazon_domains_allowed"
    else:
        raise AssertionError("non-Amazon search domains must be rejected")
