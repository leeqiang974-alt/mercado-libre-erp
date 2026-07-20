import os
from pathlib import Path
import sys
from uuid import uuid4

from playwright.sync_api import sync_playwright
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app.models.collection_job import CollectionJob, CollectionJobStatus  # noqa: E402
from app.models.source_product import SourceProduct, SourceProductStatus  # noqa: E402
from app.services.source_products import create_source_product  # noqa: E402


DATABASE_URL = os.getenv(
    "MEASUREMENT_SMOKE_DATABASE_URL",
    "postgresql+psycopg://meli:meli@127.0.0.1:5432/amazon_meli",
)
APP_URL = os.getenv("MEASUREMENT_SMOKE_APP_URL", "http://127.0.0.1:5173")
CHROME = Path(r"C:\Program Files\Google\Chrome\Application\chrome.exe")


def seed_source() -> tuple[sessionmaker, int, int, str]:
    session_factory = sessionmaker(bind=create_engine(DATABASE_URL, pool_pre_ping=True))
    marker = uuid4().hex[:10]
    title = f"Measurement integration {marker}"
    source_url = "https://www.amazon.com/dp/B0SMOKE001"
    with session_factory() as db:
        source = create_source_product(
            db,
            source_url=source_url,
            status=SourceProductStatus.COLLECTED,
            snapshot={
                "source_url": source_url,
                "title": title,
                "price": {"amount": 19.99, "currency": "USD"},
                "brand": "Smoke",
                "images": [],
                "measurements": {
                    "item_weight": {
                        "value": 1.2,
                        "unit": "lb",
                        "raw": "1.2 pounds",
                        "source_label": "Item Weight",
                    },
                    "package_dimensions": {
                        "length": 30,
                        "width": 20,
                        "height": 10,
                        "unit": "cm",
                        "raw": "30 x 20 x 10 cm",
                        "source_label": "Package Dimensions",
                    },
                },
            },
        )
        job = CollectionJob(
            source_url=source_url,
            source_identity=f"amazon.com:B0SMOKE001:{marker}",
            target_site_id="MLM",
            status=CollectionJobStatus.COMPLETED,
            message="measurement integration smoke",
            source_product_id=source.id,
        )
        db.add(job)
        db.commit()
        db.refresh(job)
        return session_factory, source.id, job.id, title


def cleanup(session_factory: sessionmaker, source_id: int, job_id: int) -> None:
    with session_factory() as db:
        job = db.get(CollectionJob, job_id)
        if job is not None:
            db.delete(job)
            db.flush()
        source = db.get(SourceProduct, source_id)
        if source is not None:
            db.delete(source)
        db.commit()


def main() -> None:
    session_factory, source_id, job_id, title = seed_source()
    try:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True, executable_path=str(CHROME))
            page = browser.new_page(viewport={"width": 1280, "height": 900})
            page.goto(APP_URL, wait_until="domcontentloaded")
            page.get_by_role("button", name="Import", exact=True).click()
            row = page.locator(".collection-job").filter(has_text=title)
            row.wait_for()
            row.get_by_role("button", name="Review source", exact=True).click()
            row.get_by_text("Item Weight", exact=True).wait_for()
            row.get_by_text("1.2 pounds", exact=True).wait_for()
            row.get_by_text("Package Dimensions", exact=True).wait_for()
            row.get_by_text("30 x 20 x 10 cm", exact=True).wait_for()
            assert row.locator(".source-measurements > span").count() == 2
            browser.close()
        print({"job_id": job_id, "source_id": source_id, "measurement_cards": 2})
    finally:
        cleanup(session_factory, source_id, job_id)


if __name__ == "__main__":
    main()
