import pytest

from app.services.amazon.collector import CollectionStatus, collect_amazon_page


NORMAL_HTML = """
<span id="productTitle">Collector Bottle</span>
<span class="a-price"><span class="a-offscreen">$12.50</span></span>
<img id="landingImage" src="https://example.com/bottle.jpg" />
"""


@pytest.mark.asyncio
async def test_collect_amazon_page_uses_fetcher_and_returns_draft():
    async def fake_fetcher(url: str) -> str:
        assert url == "https://www.amazon.com/dp/B000TEST"
        return NORMAL_HTML

    result = await collect_amazon_page(
        "https://www.amazon.com/dp/B000TEST",
        target_site_id="MLM",
        html_fetcher=fake_fetcher,
    )

    assert result.status == CollectionStatus.COLLECTED
    assert result.draft is not None
    assert result.draft.title == "Collector Bottle"
    assert result.draft.price == 12.5


@pytest.mark.asyncio
async def test_collect_amazon_page_marks_captcha_as_manual_action():
    async def fake_fetcher(url: str) -> str:
        return "<html><title>Robot Check</title><form action='/errors/validateCaptcha'></form></html>"

    result = await collect_amazon_page(
        "https://www.amazon.com/dp/B000TEST",
        target_site_id="MLM",
        html_fetcher=fake_fetcher,
    )

    assert result.status == CollectionStatus.NEEDS_MANUAL_ACTION
    assert result.draft is None
    assert "challenge" in result.message.lower()
