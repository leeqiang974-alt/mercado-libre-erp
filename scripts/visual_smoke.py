from pathlib import Path

from playwright.sync_api import Page, sync_playwright


ROOT = Path(__file__).resolve().parents[1]
ARTIFACTS = ROOT / "artifacts"
CHROME = Path(r"C:\Program Files\Google\Chrome\Application\chrome.exe")
APP_URL = "http://127.0.0.1:5173"


def select_first_draft(page: Page) -> None:
    page.get_by_role("button", name="Drafts", exact=True).click()
    rows = page.locator(".draft-row")
    rows.first.wait_for(state="visible")
    assert rows.count() >= 1, "Expected at least one persisted draft"
    rows.nth(0).click()
    page.get_by_role("heading", name="Product draft", exact=True).wait_for()
    page.locator(".product-summary").wait_for(state="visible")


def inspect_publish_workspace(page: Page) -> dict[str, object]:
    page.get_by_role("button", name="Publish", exact=True).click()
    page.get_by_role("heading", name="Publish workspace", exact=True).wait_for()
    site_label = page.locator("label").filter(has_text="Mercado Libre site")
    assert site_label.count() == 1, "Expected one Mercado Libre site selector"
    site_select = site_label.locator("select")
    option_count = site_select.locator("option").count()
    assert option_count == 18, f"Expected 18 Mercado Libre sites, got {option_count}"
    offers = page.locator(".listing-choice button")
    offers.nth(0).wait_for()
    assert offers.count() == 2, "Expected Classic and Premium offer controls"
    classic = offers.nth(0)
    premium = offers.nth(1)
    assert "Classic" in classic.inner_text()
    assert "Premium" in premium.inner_text()
    page.wait_for_function(
        "() => Array.from(document.querySelectorAll('.listing-choice button')).every((button) => !button.disabled)",
        timeout=7000,
    )
    page.get_by_text("FULL is always excluded.", exact=False).wait_for()
    return {
        "site_options": option_count,
        "classic_enabled": classic.is_enabled(),
        "premium_enabled": premium.is_enabled(),
        "horizontal_overflow": page.evaluate("document.documentElement.scrollWidth > innerWidth"),
    }


def main() -> None:
    ARTIFACTS.mkdir(exist_ok=True)
    console_errors: list[str] = []
    failed_responses: list[str] = []
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True, executable_path=str(CHROME))

        desktop = browser.new_page(viewport={"width": 1440, "height": 1000})
        desktop.on(
            "console",
            lambda message: console_errors.append(message.text)
            if message.type == "error"
            else None,
        )
        desktop.on(
            "response",
            lambda response: failed_responses.append(f"{response.status} {response.url}")
            if response.status >= 400
            else None,
        )
        desktop.goto(APP_URL, wait_until="networkidle")
        desktop.get_by_text("Integration readiness", exact=True).wait_for()
        desktop.screenshot(path=ARTIFACTS / "overview-desktop.png", full_page=True)
        select_first_draft(desktop)
        desktop.screenshot(path=ARTIFACTS / "draft-desktop.png", full_page=True)
        desktop_result = inspect_publish_workspace(desktop)
        desktop.screenshot(path=ARTIFACTS / "publish-desktop.png", full_page=True)

        mobile = browser.new_page(viewport={"width": 390, "height": 844})
        mobile.on(
            "console",
            lambda message: console_errors.append(message.text)
            if message.type == "error"
            else None,
        )
        mobile.on(
            "response",
            lambda response: failed_responses.append(f"{response.status} {response.url}")
            if response.status >= 400
            else None,
        )
        mobile.goto(APP_URL, wait_until="networkidle")
        select_first_draft(mobile)
        mobile_result = inspect_publish_workspace(mobile)
        mobile.screenshot(path=ARTIFACTS / "publish-mobile.png", full_page=True)

        browser.close()

    assert not desktop_result["horizontal_overflow"], "Desktop page overflows horizontally"
    assert not mobile_result["horizontal_overflow"], "Mobile page overflows horizontally"
    assert not console_errors, f"Browser console errors: {console_errors}"
    assert not failed_responses, f"Failed browser responses: {failed_responses}"
    print(
        {
            "desktop": desktop_result,
            "mobile": mobile_result,
            "console_errors": console_errors,
            "failed_responses": failed_responses,
            "screenshots": str(ARTIFACTS),
        }
    )


if __name__ == "__main__":
    main()
