from collections.abc import Awaitable, Callable
from enum import Enum

from pydantic import BaseModel

from app.schemas.drafts import ProductDraftCreate
from app.services.amazon.normalizer import normalize_amazon_product
from app.services.amazon.parser import parse_amazon_html


class CollectionStatus(str, Enum):
    COLLECTED = "collected"
    NEEDS_MANUAL_ACTION = "needs_manual_action"
    FAILED = "failed"


class CollectionResult(BaseModel):
    status: CollectionStatus
    source_url: str
    message: str
    draft: ProductDraftCreate | None = None


HtmlFetcher = Callable[[str], Awaitable[str]]


CHALLENGE_MARKERS = [
    "robot check",
    "validatecaptcha",
    "enter the characters you see below",
    "sorry, we just need to make sure you're not a robot",
    "captcha",
]


def requires_manual_action(html: str) -> bool:
    lowered = html.lower()
    return any(marker in lowered for marker in CHALLENGE_MARKERS)


async def fetch_amazon_html_with_playwright(url: str) -> str:
    from playwright.async_api import async_playwright

    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(headless=True)
        page = await browser.new_page(
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            )
        )
        try:
            await page.goto(url, wait_until="domcontentloaded", timeout=30_000)
            await page.wait_for_timeout(1_000)
            return await page.content()
        finally:
            await browser.close()


async def collect_amazon_page(
    source_url: str,
    target_site_id: str,
    html_fetcher: HtmlFetcher | None = None,
) -> CollectionResult:
    fetcher = html_fetcher or fetch_amazon_html_with_playwright
    try:
        html = await fetcher(source_url)
    except Exception as exc:
        return CollectionResult(
            status=CollectionStatus.FAILED,
            source_url=source_url,
            message=f"Amazon page collection failed: {exc}",
        )
    if requires_manual_action(html):
        return CollectionResult(
            status=CollectionStatus.NEEDS_MANUAL_ACTION,
            source_url=source_url,
            message="Amazon challenge detected; manual action required.",
        )
    parsed = parse_amazon_html(html, source_url)
    draft = normalize_amazon_product(parsed, target_site_id=target_site_id)
    return CollectionResult(
        status=CollectionStatus.COLLECTED,
        source_url=source_url,
        message="collected",
        draft=draft,
    )
