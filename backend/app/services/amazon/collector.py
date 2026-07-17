from collections.abc import Awaitable, Callable
from enum import Enum
from urllib.parse import urlparse

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
    source_product_id: int | None = None
    draft_id: int | None = None


HtmlFetcher = Callable[[str], Awaitable[str]]


CHALLENGE_MARKERS = [
    "robot check",
    "validatecaptcha",
    "enter the characters you see below",
    "sorry, we just need to make sure you're not a robot",
    "captcha",
]

AMAZON_DOMAINS = {
    "amazon.com",
    "amazon.ca",
    "amazon.com.mx",
    "amazon.com.br",
    "amazon.co.uk",
    "amazon.de",
    "amazon.fr",
    "amazon.it",
    "amazon.es",
    "amazon.nl",
    "amazon.co.jp",
    "amazon.in",
    "amazon.com.au",
    "amazon.sg",
    "amazon.ae",
    "amazon.sa",
}


def is_allowed_amazon_url(url: str) -> bool:
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        return False
    host = parsed.hostname.lower().rstrip(".")
    return any(host == domain or host.endswith(f".{domain}") for domain in AMAZON_DOMAINS)


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
            if not is_allowed_amazon_url(page.url):
                raise ValueError("Amazon navigation redirected to a disallowed host.")
            await page.wait_for_timeout(1_000)
            return await page.content()
        finally:
            await browser.close()


async def collect_amazon_page(
    source_url: str,
    target_site_id: str,
    html_fetcher: HtmlFetcher | None = None,
) -> CollectionResult:
    if not is_allowed_amazon_url(source_url):
        return CollectionResult(
            status=CollectionStatus.FAILED,
            source_url=source_url,
            message="Only public Amazon product URLs are allowed.",
        )
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
    if not parsed["title"] or parsed["price"]["amount"] is None or not parsed["images"]:
        return CollectionResult(
            status=CollectionStatus.NEEDS_MANUAL_ACTION,
            source_url=source_url,
            message="Amazon product page is incomplete; manual action required.",
        )
    draft = normalize_amazon_product(parsed, target_site_id=target_site_id)
    return CollectionResult(
        status=CollectionStatus.COLLECTED,
        source_url=source_url,
        message="collected",
        draft=draft,
    )
