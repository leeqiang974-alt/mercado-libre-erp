import os
from pathlib import Path
import sys
from uuid import uuid4

from playwright.sync_api import sync_playwright
from sqlalchemy import create_engine, delete
from sqlalchemy.orm import sessionmaker


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app.models.audit_event import AuditEvent  # noqa: E402
from app.models.product_draft import ProductDraft  # noqa: E402
from app.models.review_result import ReviewResult  # noqa: E402
from app.models.registry import import_all_models  # noqa: E402
from app.schemas.reviews import ReviewResponse  # noqa: E402
from app.services.reviews import persist_review_result  # noqa: E402


DATABASE_URL = os.getenv(
    "REVIEW_TELEMETRY_SMOKE_DATABASE_URL",
    "postgresql+psycopg://meli:meli@127.0.0.1:5432/amazon_meli",
)
APP_URL = os.getenv("REVIEW_TELEMETRY_SMOKE_APP_URL", "http://127.0.0.1:5173")
CHROME = Path(r"C:\Program Files\Google\Chrome\Application\chrome.exe")


def seed_review() -> tuple[sessionmaker, int, int, str]:
    import_all_models()
    session_factory = sessionmaker(bind=create_engine(DATABASE_URL, pool_pre_ping=True))
    marker = uuid4().hex[:10]
    title = f"Review telemetry integration {marker}"
    with session_factory() as db:
        draft = ProductDraft(
            title=title,
            description="Temporary integration smoke draft.",
            target_site_id="MLM",
            price=100,
            currency="MXN",
            stock=1,
            image_urls_json=["https://httpbin.org/image/png"],
        )
        db.add(draft)
        db.flush()
        result = persist_review_result(
            db,
            draft.id,
            ReviewResponse(
                provider="claude",
                decision="needs_human_review",
                risk_level="medium",
                reason_codes=["integration_smoke"],
                reasons=["Temporary telemetry verification."],
                input_tokens=321,
                output_tokens=45,
                total_tokens=366,
                provider_request_id=f"req_smoke_{marker}",
            ),
            model="claude-smoke-model",
            prompt_version="meli-safety-v1",
            duration_ms=678,
        )
        return session_factory, draft.id, result.id, title


def cleanup(session_factory: sessionmaker, draft_id: int) -> None:
    with session_factory() as db:
        db.execute(delete(ReviewResult).where(ReviewResult.product_draft_id == draft_id))
        db.execute(
            delete(AuditEvent).where(
                AuditEvent.entity_type == "product_draft",
                AuditEvent.entity_id == str(draft_id),
            )
        )
        draft = db.get(ProductDraft, draft_id)
        if draft is not None:
            db.delete(draft)
        db.commit()


def main() -> None:
    session_factory, draft_id, review_id, title = seed_review()
    try:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True, executable_path=str(CHROME))
            page = browser.new_page(viewport={"width": 1280, "height": 900})
            page.goto(APP_URL, wait_until="domcontentloaded")
            page.get_by_role("button", name="Drafts", exact=True).click()
            row = page.locator(".draft-row").filter(has_text=title)
            row.wait_for()
            row.click()
            page.get_by_role("button", name="History", exact=True).click()
            history = page.locator(".review-history-row").filter(has_text="req_smoke_")
            history.wait_for()
            text = history.inner_text()
            assert "claude-smoke-model" in text
            assert "678 ms" in text
            assert "366 tokens" in text
            assert "321 in / 45 out" in text
            assert "needs_human_review" in text
            browser.close()
        print({"draft_id": draft_id, "review_id": review_id, "telemetry_visible": True})
    finally:
        cleanup(session_factory, draft_id)


if __name__ == "__main__":
    main()
