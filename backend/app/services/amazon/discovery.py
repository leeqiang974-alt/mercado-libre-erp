from dataclasses import dataclass
import os
from urllib.parse import quote_plus, urlparse

from bs4 import BeautifulSoup

from app.services.amazon.collector import (
    amazon_browser_headless,
    amazon_browser_language,
    amazon_marketplace_domain,
    normalize_amazon_product_url,
    requires_manual_action,
)


@dataclass(frozen=True)
class AmazonDiscoveryResult:
    search_url: str
    product_urls: list[str]
    challenge_detected: bool = False


def build_amazon_search_url(domain: str, keyword: str, page: int = 1) -> str:
    hostname = domain.strip().lower().removeprefix("https://").removeprefix("http://").strip("/")
    search_url = f"https://{hostname}/s?k={quote_plus(keyword.strip())}&page={max(1, page)}"
    if amazon_marketplace_domain(search_url) is None:
        raise ValueError("only_public_amazon_domains_allowed")
    return search_url


def extract_amazon_search_product_urls(html: str, search_url: str, limit: int) -> list[str]:
    soup = BeautifulSoup(html, "html.parser")
    parsed_search = urlparse(search_url)
    urls: list[str] = []
    for node in soup.select('[data-component-type="s-search-result"][data-asin]'):
        asin = str(node.get("data-asin") or "").strip().upper()
        if len(asin) != 10 or not asin.isalnum():
            continue
        try:
            product_url = normalize_amazon_product_url(
                f"{parsed_search.scheme}://{parsed_search.netloc}/dp/{asin}"
            )
        except ValueError:
            continue
        if product_url not in urls:
            urls.append(product_url)
        if len(urls) >= limit:
            break
    return urls


async def discover_amazon_products(domain: str, keyword: str, limit: int, page: int = 1) -> AmazonDiscoveryResult:
    search_url = build_amazon_search_url(domain, keyword, page)
    from playwright.async_api import TimeoutError as PlaywrightTimeoutError
    from playwright.async_api import async_playwright

    locale, accept_language = amazon_browser_language(search_url)
    headless = amazon_browser_headless()
    async with async_playwright() as playwright:
        profile_dir = os.getenv("AMAZON_BROWSER_PROFILE_DIR", "").strip()
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
            await page.goto(search_url, wait_until="domcontentloaded", timeout=30_000)
            try:
                await page.wait_for_selector(
                    '[data-component-type="s-search-result"][data-asin]', timeout=12_000
                )
            except PlaywrightTimeoutError:
                pass
            await page.wait_for_timeout(750)
            html = await page.content()
            return AmazonDiscoveryResult(
                search_url=search_url,
                product_urls=extract_amazon_search_product_urls(html, search_url, limit),
                challenge_detected=requires_manual_action(html),
            )
        finally:
            await context.close()
