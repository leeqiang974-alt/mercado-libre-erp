import json
import os
from pathlib import Path

from playwright.sync_api import Page, sync_playwright


ROOT = Path(__file__).resolve().parents[1]
ARTIFACTS = ROOT / "artifacts"
RUNTIME_TEMP = ARTIFACTS / "runtime-temp"
CHROME = Path(r"C:\Program Files\Google\Chrome\Application\chrome.exe")
APP_URL = os.getenv("VISUAL_APP_URL", "http://127.0.0.1:5173")


def mock_store_capabilities(page: Page) -> None:
    page.route("**/api/drafts", fulfill_drafts)
    page.route(
        "**/api/drafts/2/listing-config?optional=true",
        fulfill_listing_config,
    )
    page.route("**/api/drafts/2/listing-config", fulfill_listing_config)
    page.route("**/api/drafts/2/attribute-suggestions?*", fulfill_attribute_suggestions)
    page.route("**/api/metadata/categories/MLM123/attributes", fulfill_category_attributes)
    page.route("**/api/imports/amazon-url/jobs?*", fulfill_collection_jobs)
    page.route("**/api/imports/source-products/**", fulfill_source_product)
    page.route(
        "**/api/stores",
        lambda route: route.fulfill(
            status=200,
            content_type="application/json",
            body=(
                '[{"id":"9001","site_id":"MLM","seller_id":"visual-test",'
                '"display_name":"Visual Test Store","oauth_status":"connected"}]'
            ),
        ),
    )
    page.route(
        "**/api/stores/9001/shipping-options",
        lambda route: route.fulfill(
            status=200,
            content_type="application/json",
            body=(
                '{"store_id":9001,"site_id":"MLM","verified":true,"options":['
                '{"mode":"me2","logistic_type":"drop_off"},'
                '{"mode":"me2","logistic_type":"self_service"}]}'
            ),
        ),
    )
    page.route("**/api/reviews/drafts/*", fulfill_review_history)


def fulfill_listing_config(route) -> None:
    if route.request.method == "GET":
        route.fulfill(status=200, content_type="application/json", body="null")
        return
    body = json.loads(route.request.post_data or "{}")
    response = {
        "id": 9201,
        "product_draft_id": 2,
        **body,
        "attributes": [
            {
                **attribute,
                "value_name": str(attribute.get("value_name") or "").strip(),
                "value_id": attribute.get("value_id"),
            }
            for attribute in body.get("attributes", [])
        ],
        "created_at": "2026-07-20T12:00:00Z",
        "updated_at": "2026-07-20T12:00:01Z",
    }
    route.fulfill(status=200, content_type="application/json", body=json.dumps(response))


def _source_image(color: str) -> str:
    svg = (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="120" height="120">'
        f'<rect width="120" height="120" fill="{color}"/></svg>'
    )
    from urllib.parse import quote

    return f"data:image/svg+xml,{quote(svg)}"


def fulfill_drafts(route) -> None:
    draft = {
        "id": 2,
        "source_product_id": 8001,
        "source_variant_asin": "B000TEST03",
        "source_variant_attributes": {"Color": "Blue", "Size": "32 oz"},
        "title": "TrailPro Variant Bottle",
        "description": "Insulated bottle.",
        "brand": "TrailPro",
        "target_site_id": "MLM",
        "target_category_id": "",
        "condition": "new",
        "source_price": 24.99,
        "source_currency": "USD",
        "price": 599,
        "currency": "MXN",
        "stock": 1,
        "listing_type_id": "",
        "image_urls": [_source_image("#2563eb")],
        "attributes": [],
        "status": "draft",
        "risk_status": "unreviewed",
    }
    route.fulfill(status=200, content_type="application/json", body=json.dumps([draft]))


def fulfill_category_attributes(route) -> None:
    attributes = {
        "verified": True,
        "attributes": [
            {
                "id": "COLOR",
                "name": "Color principal",
                "value_type": "list",
                "values": [{"id": "52028", "name": "Blue"}, {"id": "52055", "name": "Black"}],
                "tags": {"variation_attribute": True},
            },
            {
                "id": "SIZE",
                "name": "Talla",
                "value_type": "list",
                "values": [{"id": "S", "name": "Small"}],
                "tags": {"variation_attribute": True, "required": True},
            },
            {
                "id": "BRAND",
                "name": "Marca",
                "value_type": "string",
                "values": [],
                "tags": {"required": True},
            },
        ]
    }
    route.fulfill(status=200, content_type="application/json", body=json.dumps(attributes))


def fulfill_attribute_suggestions(route) -> None:
    response = {
        "product_draft_id": 2,
        "category_id": "MLM123",
        "source_variant_asin": "B000TEST03",
        "listing_strategy": "one_source_asin_per_item",
        "suggestions": [
            {
                "source_name": "Color",
                "source_value": "Blue",
                "attribute_id": "COLOR",
                "attribute_name": "Color principal",
                "value_name": "Blue",
                "value_id": "52028",
                "confidence": 1,
                "match_reason": "exact_attribute_name",
                "required": False,
                "variation_attribute": True,
                "can_apply": True,
            },
            {
                "source_name": "Size",
                "source_value": "32 oz",
                "attribute_id": "SIZE",
                "attribute_name": "Talla",
                "value_name": "32 oz",
                "value_id": None,
                "confidence": 0.95,
                "match_reason": "semantic_attribute_alias",
                "required": True,
                "variation_attribute": True,
                "can_apply": False,
            },
            {
                "source_name": "Brand",
                "source_value": "TrailPro",
                "attribute_id": "BRAND",
                "attribute_name": "Marca",
                "value_name": "TrailPro",
                "value_id": None,
                "confidence": 0.95,
                "match_reason": "semantic_attribute_alias",
                "required": True,
                "variation_attribute": False,
                "can_apply": True,
            },
        ],
        "unmatched_source_attributes": {},
    }
    route.fulfill(status=200, content_type="application/json", body=json.dumps(response))


def fulfill_collection_jobs(route) -> None:
    if route.request.url.endswith("/jobs/batch"):
        body = json.loads(route.request.post_data or "{}")
        items = [
            {
                "input_url": source_url,
                "normalized_url": "",
                "outcome": "invalid",
                "detail": "only_public_amazon_product_urls_allowed",
                "job": None,
            }
            for source_url in body.get("source_urls", [])
        ]
        route.fulfill(
            status=200,
            content_type="application/json",
            body=json.dumps(
                {
                    "created_count": 0,
                    "duplicate_count": 0,
                    "existing_count": 0,
                    "invalid_count": len(items),
                    "items": items,
                }
            ),
        )
        return
    row = {
        "id": 7001,
        "source_url": "https://amazon.com/dp/B000TEST01",
        "target_site_id": "MLM",
        "status": "completed",
        "message": "collected",
        "source_product_id": 8001,
        "draft_id": 2,
        "created_at": "2026-07-20T12:00:00",
        "started_at": "2026-07-20T12:00:01",
        "completed_at": "2026-07-20T12:00:04",
        "source_product": {
            "id": 8001,
            "asin": "B000TEST01",
            "status": "collected",
            "collection_method": "browser_page",
            "title": "TrailPro Variant Bottle",
            "brand": "TrailProUltraLongUnbrokenOutdoorEquipmentBrandNameForMobileLayout",
            "source_price": 24.99,
            "source_currency": "USD",
            "primary_image_url": _source_image("#2563eb"),
            "image_count": 3,
            "variant_count": 3,
            "has_snapshot": True,
            "collection_error": "",
        },
    }
    route.fulfill(status=200, content_type="application/json", body=json.dumps([row]))


def fulfill_source_product(route) -> None:
    if "/variants/" in route.request.url:
        asin = route.request.url.split("/variants/", 1)[1].split("/", 1)[0]
        body = json.loads(route.request.post_data or "{}")
        draft = {
            "id": 8103,
            "source_product_id": 8001,
            "source_variant_asin": asin,
            "source_variant_attributes": {"Color": "Blue", "Size": "32 oz"},
            "title": "TrailPro Variant Bottle",
            "description": "Insulated bottle.",
            "brand": "TrailPro",
            "target_site_id": body.get("target_site_id", "MLM"),
            "target_category_id": "",
            "condition": "new",
            "source_price": 24.99,
            "source_currency": "USD",
            "price": None,
            "currency": "MXN",
            "stock": 1,
            "listing_type_id": "",
            "image_urls": [],
            "attributes": [],
            "status": "draft",
            "risk_status": "unreviewed",
        }
        route.fulfill(status=200, content_type="application/json", body=json.dumps(draft))
        return
    source = {
        "id": 8001,
        "source": "amazon_page",
        "source_url": "https://amazon.com/dp/B000TEST01",
        "asin": "B000TEST01",
        "status": "collected",
        "collection_method": "browser_page",
        "collected_at": "2026-07-20T12:00:04",
        "collection_error": "",
        "snapshot": {
            "source_url": "https://amazon.com/dp/B000TEST01",
            "title": "TrailPro Variant Bottle",
            "price": {"amount": 24.99, "currency": "USD"},
            "brand": "TrailProUltraLongUnbrokenOutdoorEquipmentBrandNameForMobileLayout",
            "bullets": [
                "Leak proof lid",
                "ThreeSizesWithAnExtremelyLongUnbrokenSourceBulletForMobileOverflowValidation",
            ],
            "description": "Insulated bottle.",
            "images": [
                _source_image("#2563eb"),
                _source_image("#16803c"),
                _source_image("#d92d20"),
            ],
            "variants": [
                {"asin": "B000TEST01", "attributes": {"Color": "Black", "Size": "20 oz"}, "image_urls": [], "selected": True},
                {"asin": "B000TEST02", "attributes": {"Color": "Blue", "Size": "20 oz"}, "image_urls": [], "selected": False},
                {"asin": "B000TEST03", "attributes": {"Color": "Blue", "Size": "32 oz SuperInsulatedOutdoorExpeditionEdition"}, "image_urls": [], "selected": False},
            ],
            "technical_details": {"Material": "Stainless steel"},
        },
    }
    route.fulfill(status=200, content_type="application/json", body=json.dumps(source))


def fulfill_review_history(route) -> None:
    draft_id = int(route.request.url.rstrip("/").rsplit("/", 1)[-1])
    rows = [
        {
            "id": 3,
            "product_draft_id": draft_id,
            "provider": "claude+nvidia_behavioral_audit",
            "model": "nvidia-test+claude-test",
            "prompt_version": "meli-safety-v1+meli-safety-v1",
            "duration_ms": 842,
            "provider_status": "completed",
            "decision": "pass",
            "risk_level": "low",
            "reason_codes": [],
            "reasons": [],
            "suggested_changes": {},
            "created_at": "2026-07-20T12:00:00",
        },
        {
            "id": 2,
            "product_draft_id": draft_id,
            "provider": "claude",
            "model": "claude-test",
            "prompt_version": "meli-safety-v1",
            "duration_ms": 521,
            "provider_status": "completed",
            "decision": "pass",
            "risk_level": "low",
            "reason_codes": [],
            "reasons": [],
            "suggested_changes": {},
            "created_at": "2026-07-20T12:00:00",
        },
        {
            "id": 1,
            "product_draft_id": draft_id,
            "provider": "nvidia",
            "model": "nvidia-test",
            "prompt_version": "meli-safety-v1",
            "duration_ms": 321,
            "provider_status": "completed",
            "decision": "pass",
            "risk_level": "low",
            "reason_codes": [],
            "reasons": [],
            "suggested_changes": {},
            "created_at": "2026-07-20T12:00:00",
        },
    ]
    route.fulfill(status=200, content_type="application/json", body=json.dumps(rows))


def select_first_draft(page: Page) -> None:
    page.get_by_role("button", name="Drafts", exact=True).click()
    rows = page.locator(".draft-row")
    rows.first.wait_for(state="visible")
    assert rows.count() >= 1, "Expected at least one persisted draft"
    rows.nth(0).click()
    page.get_by_role("heading", name="Product draft", exact=True).wait_for()
    page.locator(".product-summary").wait_for(state="visible")
    page.get_by_text("Amazon variant · B000TEST03", exact=True).wait_for()
    assert page.locator(".variant-provenance > div span").count() == 2


def inspect_review_history(page: Page) -> dict[str, object]:
    page.get_by_role("button", name="History", exact=True).click()
    rows = page.locator(".review-history-row")
    rows.nth(2).wait_for(state="visible")
    assert rows.count() == 3, f"Expected 3 provider review history rows, got {rows.count()}"
    text = rows.all_inner_texts()
    assert any("claude-test" in row and "meli-safety-v1" in row for row in text)
    assert any("nvidia-test" in row and "321 ms" in row for row in text)
    assert all("pass" in row for row in text)
    body = page.locator("body").inner_text()
    assert "api-key" not in body.lower()
    assert "Draft JSON" not in body
    return {
        "review_rows": rows.count(),
        "horizontal_overflow": page.evaluate("document.documentElement.scrollWidth > innerWidth"),
    }


def inspect_import_workspace(page: Page) -> dict[str, object]:
    page.get_by_role("button", name="Import", exact=True).click()
    page.get_by_role("heading", name="Amazon import", exact=True).wait_for()
    site_label = page.locator("label").filter(has_text="Target Mercado Libre site")
    option_count = site_label.locator("select option").count()
    assert option_count == 18, f"Expected 18 import target sites, got {option_count}"
    page.get_by_role("tab", name="URL collector", exact=True).wait_for()
    page.get_by_role("tab", name="HTML snapshot", exact=True).click()
    page.get_by_label("Amazon HTML snapshot", exact=True).wait_for()
    page.get_by_role("tab", name="URL collector", exact=True).click()
    page.get_by_text("TrailPro Variant Bottle", exact=True).wait_for()
    page.get_by_role("button", name="Review source", exact=True).click()
    page.get_by_text("Blue · 32 oz SuperInsulatedOutdoorExpeditionEdition", exact=True).wait_for()
    source_images = page.locator(".source-image-gallery img").count()
    source_variants = page.locator(".source-variant-list > span").count()
    assert source_images == 3, f"Expected 3 source images, got {source_images}"
    assert source_variants == 3, f"Expected 3 source variants, got {source_variants}"
    page.get_by_role("button", name="Create MLM draft", exact=True).last.click()
    page.get_by_role("button", name="Draft #8103", exact=True).wait_for()
    url_input = page.get_by_label("Amazon product URLs", exact=True)
    url_input.fill("https://example.com/not-amazon\nnot-a-url")
    page.get_by_role("button", name="Add 2 to queue", exact=True).click()
    page.locator(".batch-result").wait_for()
    batch_result_count = page.locator(".batch-result-row").count()
    assert batch_result_count == 2, f"Expected 2 batch result rows, got {batch_result_count}"
    page.get_by_text("2 invalid", exact=True).wait_for()
    page.get_by_role("tab", name="HTML snapshot", exact=True).click()
    assert page.get_by_label("Amazon product URL", exact=True).input_value() == ""
    page.get_by_role("tab", name="URL collector", exact=True).click()
    return {
        "site_options": option_count,
        "job_count": page.locator(".collection-job").count(),
        "batch_result_count": batch_result_count,
        "source_images": source_images,
        "source_variants": source_variants,
        "horizontal_overflow": page.evaluate("document.documentElement.scrollWidth > innerWidth"),
    }


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
    shipping = page.locator(".shipping-choice select")
    shipping.wait_for()
    shipping.locator("option").nth(2).wait_for(state="attached", timeout=7000)
    assert shipping.locator("option").count() == 3
    assert "fulfillment" not in shipping.inner_text().lower()
    shipping.select_option("me2:self_service")
    page.get_by_text("FULL is filtered out and cannot be saved.", exact=False).wait_for()
    page.get_by_label("Category ID", exact=True).fill("MLM123")
    page.get_by_role("button", name="Load attributes", exact=True).click()
    page.get_by_text("Amazon variant B000TEST03", exact=True).wait_for()
    suggestions = page.locator(".attribute-suggestion")
    assert suggestions.count() == 3
    page.get_by_role("button", name="Apply exact matches", exact=True).click()
    assert page.get_by_label("Color principal", exact=True).input_value() == "Blue"
    assert page.get_by_label("Marca *", exact=True).input_value() == "TrailPro"
    assert page.get_by_label("Talla *", exact=True).input_value() == ""
    save_config = page.get_by_role("button", name="Save listing configuration", exact=True)
    assert save_config.is_disabled(), "Missing required size must block config save"
    page.get_by_label("Talla *", exact=True).fill(" 32 oz ")
    assert save_config.is_enabled(), "Completing required attributes should unlock config save"
    save_config.click()
    page.get_by_text("Saved as non-FULL", exact=True).wait_for()
    configured = page.locator(".publish-progress > div").filter(has_text="Configured")
    page.wait_for_function(
        "element => element.classList.contains('ready')",
        arg=configured.element_handle(),
    )
    return {
        "site_options": option_count,
        "classic_enabled": classic.is_enabled(),
        "premium_enabled": premium.is_enabled(),
        "shipping_options": shipping.locator("option").count() - 1,
        "selected_shipping": shipping.input_value(),
        "attribute_suggestions": suggestions.count(),
        "required_attribute_gate": True,
        "horizontal_overflow": page.evaluate("document.documentElement.scrollWidth > innerWidth"),
    }


def inspect_stores_workspace(page: Page) -> dict[str, object]:
    page.get_by_role("button", name="Stores", exact=True).click()
    page.get_by_role("heading", name="Authorized stores", exact=True).wait_for()
    page.get_by_role("button", name="Connect store", exact=True).wait_for()
    assert "token_reference" not in page.locator("body").inner_text()
    return {
        "connect_available": page.get_by_role("button", name="Connect store").is_enabled(),
        "horizontal_overflow": page.evaluate("document.documentElement.scrollWidth > innerWidth"),
    }


def main() -> None:
    ARTIFACTS.mkdir(exist_ok=True)
    RUNTIME_TEMP.mkdir(exist_ok=True)
    console_errors: list[str] = []
    failed_responses: list[str] = []
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(
            headless=True,
            executable_path=str(CHROME),
            env={**os.environ, "TEMP": str(RUNTIME_TEMP), "TMP": str(RUNTIME_TEMP)},
        )

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
        mock_store_capabilities(desktop)
        desktop.goto(APP_URL, wait_until="domcontentloaded")
        desktop.get_by_text("Integration readiness", exact=True).wait_for()
        desktop.screenshot(path=ARTIFACTS / "overview-desktop.png", full_page=True)
        desktop_import = inspect_import_workspace(desktop)
        desktop.screenshot(path=ARTIFACTS / "import-desktop.png", full_page=True)
        select_first_draft(desktop)
        desktop_reviews = inspect_review_history(desktop)
        desktop.screenshot(path=ARTIFACTS / "draft-desktop.png", full_page=True)
        desktop_result = inspect_publish_workspace(desktop)
        desktop.screenshot(path=ARTIFACTS / "publish-desktop.png", full_page=True)
        desktop_stores = inspect_stores_workspace(desktop)
        desktop.screenshot(path=ARTIFACTS / "stores-desktop.png", full_page=True)

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
        mock_store_capabilities(mobile)
        mobile.goto(APP_URL, wait_until="domcontentloaded")
        mobile_import = inspect_import_workspace(mobile)
        mobile.screenshot(path=ARTIFACTS / "import-mobile.png", full_page=True)
        select_first_draft(mobile)
        mobile_reviews = inspect_review_history(mobile)
        mobile.screenshot(path=ARTIFACTS / "draft-mobile.png", full_page=True)
        mobile_result = inspect_publish_workspace(mobile)
        mobile.screenshot(path=ARTIFACTS / "publish-mobile.png", full_page=True)
        mobile_stores = inspect_stores_workspace(mobile)
        mobile.screenshot(path=ARTIFACTS / "stores-mobile.png", full_page=True)

        browser.close()

    assert not desktop_result["horizontal_overflow"], "Desktop page overflows horizontally"
    assert not mobile_result["horizontal_overflow"], "Mobile page overflows horizontally"
    assert not desktop_import["horizontal_overflow"], "Desktop import page overflows horizontally"
    assert not mobile_import["horizontal_overflow"], "Mobile import page overflows horizontally"
    assert not desktop_stores["horizontal_overflow"], "Desktop stores page overflows horizontally"
    assert not mobile_stores["horizontal_overflow"], "Mobile stores page overflows horizontally"
    assert not desktop_reviews["horizontal_overflow"], "Desktop review history overflows horizontally"
    assert not mobile_reviews["horizontal_overflow"], "Mobile review history overflows horizontally"
    assert not console_errors, f"Browser console errors: {console_errors}"
    assert not failed_responses, f"Failed browser responses: {failed_responses}"
    print(
        {
            "desktop": desktop_result,
            "mobile": mobile_result,
            "desktop_import": desktop_import,
            "mobile_import": mobile_import,
            "desktop_stores": desktop_stores,
            "mobile_stores": mobile_stores,
            "desktop_reviews": desktop_reviews,
            "mobile_reviews": mobile_reviews,
            "console_errors": console_errors,
            "failed_responses": failed_responses,
            "screenshots": str(ARTIFACTS),
        }
    )


if __name__ == "__main__":
    main()
