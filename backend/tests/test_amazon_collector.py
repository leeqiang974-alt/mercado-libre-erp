import pytest

from app.services.amazon.collector import CollectionStatus, collect_amazon_page


NORMAL_HTML = """
<input id="ASIN" value="B000TEST01" />
<span id="productTitle">Collector Bottle</span>
<span class="a-price"><span class="a-offscreen">$12.50</span></span>
<img id="landingImage" src="https://example.com/bottle.jpg" />
"""


@pytest.mark.asyncio
async def test_collect_amazon_page_uses_fetcher_and_returns_draft():
    async def fake_fetcher(url: str) -> str:
        assert url == "https://www.amazon.com/dp/B000TEST01"
        return NORMAL_HTML

    result = await collect_amazon_page(
        "https://www.amazon.com/dp/B000TEST01",
        target_site_id="MLM",
        html_fetcher=fake_fetcher,
    )

    assert result.status == CollectionStatus.COLLECTED
    assert result.draft is not None
    assert result.draft.title == "Collector Bottle"
    assert result.draft.source_price == 12.5
    assert result.draft.source_currency == "USD"
    assert result.draft.price is None
    assert result.draft.currency == "MXN"


@pytest.mark.asyncio
async def test_collect_amazon_page_marks_captcha_as_manual_action():
    async def fake_fetcher(url: str) -> str:
        return "<html><title>Robot Check</title><form action='/errors/validateCaptcha'></form></html>"

    result = await collect_amazon_page(
        "https://www.amazon.com/dp/B000TEST01",
        target_site_id="MLM",
        html_fetcher=fake_fetcher,
    )

    assert result.status == CollectionStatus.NEEDS_MANUAL_ACTION
    assert result.draft is None
    assert "challenge" in result.message.lower()


@pytest.mark.asyncio
async def test_collect_amazon_page_rejects_non_amazon_url_before_fetch():
    async def unexpected_fetcher(url: str) -> str:
        raise AssertionError("disallowed URLs must not be fetched")

    result = await collect_amazon_page(
        "http://127.0.0.1:8000/private",
        target_site_id="MLM",
        html_fetcher=unexpected_fetcher,
    )

    assert result.status == CollectionStatus.FAILED
    assert "Amazon" in result.message


@pytest.mark.asyncio
async def test_collect_amazon_page_marks_incomplete_page_for_manual_action():
    async def fake_fetcher(url: str) -> str:
        return "<html><title>Sign in</title></html>"

    result = await collect_amazon_page(
        "https://www.amazon.com/dp/B000TEST01",
        target_site_id="MLM",
        html_fetcher=fake_fetcher,
    )

    assert result.status == CollectionStatus.NEEDS_MANUAL_ACTION
    assert result.draft is None


@pytest.mark.asyncio
async def test_collect_amazon_page_retries_transient_incomplete_page():
    attempts = 0

    async def fake_fetcher(url: str) -> str:
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            return "<html><title>Loading</title></html>"
        return NORMAL_HTML

    result = await collect_amazon_page(
        "https://www.amazon.com/dp/B000TEST01",
        target_site_id="MLM",
        html_fetcher=fake_fetcher,
    )

    assert attempts == 2
    assert result.status == CollectionStatus.COLLECTED
    assert result.draft is not None
