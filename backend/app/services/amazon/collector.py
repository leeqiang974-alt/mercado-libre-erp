from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from enum import Enum
import os
from urllib.parse import urlparse

from pydantic import BaseModel

from app.schemas.drafts import ProductDraftCreate
from app.schemas.source_products import AmazonSourceSnapshot
from app.services.amazon.normalizer import normalize_amazon_product
from app.services.amazon.parser import (
    PRODUCT_IMAGE_SELECTOR,
    PRODUCT_PRICE_SELECTOR,
    PRODUCT_TITLE_SELECTOR,
    extract_displayed_asin,
    extract_amazon_asin,
    extract_snapshot_asins,
    parse_amazon_html,
)


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
    source_snapshot: AmazonSourceSnapshot | None = None
    collection_method: str = "browser_page"


@dataclass(frozen=True)
class AmazonPageFetch:
    html: str
    final_url: str
    collection_method: str


HtmlFetcher = Callable[[str], Awaitable[str | AmazonPageFetch]]


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

AMAZON_BROWSER_LOCALES = {
    "amazon.com": "en-US",
    "amazon.ca": "en-CA",
    "amazon.com.mx": "es-MX",
    "amazon.com.br": "pt-BR",
    "amazon.co.uk": "en-GB",
    "amazon.de": "de-DE",
    "amazon.fr": "fr-FR",
    "amazon.it": "it-IT",
    "amazon.es": "es-ES",
    "amazon.nl": "nl-NL",
    "amazon.co.jp": "ja-JP",
    "amazon.in": "en-IN",
    "amazon.com.au": "en-AU",
    "amazon.sg": "en-SG",
    "amazon.ae": "en-AE",
    "amazon.sa": "en-SA",
}

PRODUCT_CONTENT_READY = f"""
() => Boolean(
    document.querySelector('{PRODUCT_TITLE_SELECTOR}') &&
    document.querySelector('{PRODUCT_PRICE_SELECTOR}') &&
    document.querySelector('{PRODUCT_IMAGE_SELECTOR}')
)
"""


def is_allowed_amazon_url(url: str) -> bool:
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        return False
    host = parsed.hostname.lower().rstrip(".")
    return bool(
        extract_amazon_asin(url)
        and any(host == domain or host.endswith(f".{domain}") for domain in AMAZON_DOMAINS)
    )


def normalize_amazon_product_url(url: str) -> str:
    source_url = url.strip()
    if not is_allowed_amazon_url(source_url):
        raise ValueError("only_public_amazon_product_urls_allowed")
    parsed = urlparse(source_url)
    host = (parsed.hostname or "").lower().rstrip(".")
    domain = next(
        domain
        for domain in sorted(AMAZON_DOMAINS, key=len, reverse=True)
        if host == domain or host.endswith(f".{domain}")
    )
    asin = extract_amazon_asin(source_url)
    assert asin is not None
    return f"https://{domain}/dp/{asin}"


def amazon_marketplace_domain(url: str) -> str | None:
    parsed = urlparse(url)
    host = (parsed.hostname or "").lower().rstrip(".")
    return next(
        (
            domain
            for domain in sorted(AMAZON_DOMAINS, key=len, reverse=True)
            if host == domain or host.endswith(f".{domain}")
        ),
        None,
    )


def amazon_browser_language(url: str) -> tuple[str, str]:
    parsed = urlparse(url)
    host = (parsed.hostname or "").lower().rstrip(".")
    domain = next(
        (
            domain
            for domain in sorted(AMAZON_BROWSER_LOCALES, key=len, reverse=True)
            if host == domain or host.endswith(f".{domain}")
        ),
        "amazon.com",
    )
    locale = AMAZON_BROWSER_LOCALES[domain]
    language = locale.split("-", 1)[0]
    fallbacks = [locale]
    if language != locale:
        fallbacks.append(f"{language};q=0.9")
    if language != "en":
        fallbacks.append("en;q=0.8")
    return locale, ",".join(fallbacks)


def requires_manual_action(html: str) -> bool:
    lowered = html.lower()
    return any(marker in lowered for marker in CHALLENGE_MARKERS)


def amazon_browser_headless() -> bool:
    """Use headed Chromium by default when a virtual display is available."""
    value = os.getenv("AMAZON_BROWSER_HEADLESS", "false").strip().lower()
    return value in {"1", "true", "yes", "on"}


def validate_amazon_navigation(source_url: str, final_url: str) -> str | None:
    """Reject redirects before interpreting an Amazon landing page as product HTML."""
    expected_asin = extract_amazon_asin(source_url)
    if not expected_asin:
        return "amazon_navigation_requested_asin_missing"
    if not is_allowed_amazon_url(final_url):
        return "amazon_navigation_not_product"
    final_asin = extract_amazon_asin(final_url)
    if final_asin != expected_asin:
        return "amazon_navigation_asin_mismatch"
    return None


def validate_amazon_snapshot(source_url: str, html: str) -> dict:
    if not is_allowed_amazon_url(source_url):
        raise ValueError("only_public_amazon_product_urls_allowed")
    if requires_manual_action(html):
        raise ValueError("amazon_challenge_snapshot_rejected")
    parsed = parse_amazon_html(html, source_url)
    missing: list[str] = []
    if not parsed["title"]:
        missing.append("title")
    if parsed["price"]["amount"] is None:
        missing.append("price")
    elif not parsed["price"]["currency"]:
        missing.append("source_currency")
    if not parsed["images"]:
        missing.append("image")
    if missing:
        raise ValueError(f"amazon_snapshot_incomplete:{','.join(missing)}")
    expected_asin = extract_amazon_asin(source_url)
    displayed_asin = extract_displayed_asin(html)
    if displayed_asin and displayed_asin != expected_asin:
        raise ValueError("amazon_snapshot_identity_mismatch")
    if expected_asin not in extract_snapshot_asins(html):
        raise ValueError("amazon_snapshot_identity_mismatch")
    return parsed


async def fetch_amazon_html_with_playwright(url: str) -> AmazonPageFetch:
    from playwright.async_api import TimeoutError as PlaywrightTimeoutError
    from playwright.async_api import async_playwright

    async with async_playwright() as playwright:
        profile_dir = os.getenv("AMAZON_BROWSER_PROFILE_DIR", "").strip()
        locale, accept_language = amazon_browser_language(url)
        headless = amazon_browser_headless()
        context = await playwright.chromium.launch_persistent_context(
            profile_dir or None,
            headless=headless,
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/131.0.0.0 Safari/537.36"
            ),
            locale=locale,
            viewport={"width": 1440, "height": 1000},
            extra_http_headers={"Accept-Language": accept_language},
        )
        page = context.pages[0] if context.pages else await context.new_page()
        try:
            await page.goto(url, wait_until="domcontentloaded", timeout=30_000)
            initial_html = await page.content()
            if requires_manual_action(initial_html):
                return AmazonPageFetch(
                    html=initial_html,
                    final_url=page.url,
                    collection_method=(
                        "server_browser_headless" if headless else "server_browser_headed"
                    ),
                )
            try:
                await page.wait_for_load_state("load", timeout=8_000)
            except PlaywrightTimeoutError:
                pass
            try:
                await page.wait_for_function(PRODUCT_CONTENT_READY, timeout=12_000)
            except PlaywrightTimeoutError:
                pass
            await page.wait_for_timeout(1_000)
            return AmazonPageFetch(
                html=await page.content(),
                final_url=page.url,
                collection_method=(
                    "server_browser_headless" if headless else "server_browser_headed"
                ),
            )
        finally:
            await context.close()


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
        fetched = await fetcher(source_url)
    except Exception as exc:
        return CollectionResult(
            status=CollectionStatus.FAILED,
            source_url=source_url,
            message=f"Amazon page collection failed; explicit retry is safe: {exc}",
        )
    if isinstance(fetched, AmazonPageFetch):
        html = fetched.html
        final_url = fetched.final_url
        collection_method = fetched.collection_method
    else:
        html = fetched
        final_url = source_url
        collection_method = "browser_page"
    if requires_manual_action(html):
        return CollectionResult(
            status=CollectionStatus.NEEDS_MANUAL_ACTION,
            source_url=source_url,
            message="Amazon challenge detected; manual action required.",
            collection_method=collection_method,
        )
    navigation_error = validate_amazon_navigation(source_url, final_url)
    if navigation_error == "amazon_navigation_not_product":
        return CollectionResult(
            status=CollectionStatus.FAILED,
            source_url=source_url,
            message="Amazon redirected this link away from the requested product; verify the ASIN.",
            collection_method=collection_method,
        )
    if navigation_error == "amazon_navigation_asin_mismatch":
        return CollectionResult(
            status=CollectionStatus.FAILED,
            source_url=source_url,
            message="Amazon redirected this link to a different ASIN; the requested product was not collected.",
            collection_method=collection_method,
        )
    try:
        parsed = validate_amazon_snapshot(source_url, html)
    except ValueError as exc:
        if str(exc).startswith("amazon_snapshot_incomplete:"):
            return CollectionResult(
                status=CollectionStatus.NEEDS_MANUAL_ACTION,
                source_url=source_url,
                message="Amazon product page is incomplete; manual action required.",
                collection_method=collection_method,
            )
        return CollectionResult(
            status=CollectionStatus.FAILED,
            source_url=source_url,
            message=f"Amazon page identity validation failed: {exc}",
            collection_method=collection_method,
        )
    draft = normalize_amazon_product(parsed, target_site_id=target_site_id)
    source_snapshot = AmazonSourceSnapshot.model_validate(parsed)
    return CollectionResult(
        status=CollectionStatus.COLLECTED,
        source_url=source_url,
        message="collected",
        draft=draft,
        source_snapshot=source_snapshot,
        collection_method=collection_method,
    )
