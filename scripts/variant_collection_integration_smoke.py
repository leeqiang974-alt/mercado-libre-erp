import os
from pathlib import Path
import subprocess
import sys
from uuid import uuid4

import httpx
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "backend"))

from app.models.collection_job import CollectionJob  # noqa: E402
from app.models.product_draft import ProductDraft  # noqa: E402
from app.models.registry import import_all_models  # noqa: E402
from scripts.isolated_runtime import (  # noqa: E402
    available_port,
    build_isolated_database_url,
    create_isolated_database,
    drop_isolated_database,
    stop_process,
    wait_for_backend,
)


ADMIN_DATABASE_URL = os.getenv(
    "VARIANT_COLLECTION_SMOKE_ADMIN_DATABASE_URL",
    "postgresql+psycopg://meli:meli@127.0.0.1:5432/amazon_meli",
)


def main() -> None:
    import_all_models()
    database_name = f"variant_collection_smoke_{uuid4().hex}"
    database_url = build_isolated_database_url(ADMIN_DATABASE_URL, database_name)
    api_port = available_port()
    api_url = f"http://127.0.0.1:{api_port}"
    backend_process: subprocess.Popen | None = None
    database_created = False
    marker = uuid4().hex[:9].upper()
    selected_asin = f"S{marker}"
    variant_asin = f"V{marker}"
    environment = os.environ.copy()
    environment.update(
        {
            "DATABASE_URL": database_url,
            "TOKEN_ENCRYPTION_KEY": f"variant-smoke-{uuid4().hex}",
            "ALLOW_LIVE_PUBLISH": "false",
        }
    )
    html = f"""
    <input id="ASIN" value="{selected_asin}" />
    <span id="productTitle">Variant collection smoke</span>
    <span class="a-price"><span class="a-offscreen">MX$199.00</span></span>
    <script>
      var imageData = {{
        'colorImages': {{
          'initial':[{{'hiRes':'https://example.com/{selected_asin}.jpg'}}],
          'Blue':[{{'hiRes':'https://example.com/{variant_asin}.jpg'}}]
        }},
        'colorToAsin': {{'Blue':{{'asin':'{variant_asin}'}}}}
      }};
    </script>
    """
    try:
        create_isolated_database(ADMIN_DATABASE_URL, database_name)
        database_created = True
        subprocess.run(
            [sys.executable, "-m", "alembic", "upgrade", "head"],
            cwd=ROOT / "backend",
            env=environment,
            check=True,
            capture_output=True,
            text=True,
        )
        backend_process = subprocess.Popen(
            [
                sys.executable,
                "-m",
                "uvicorn",
                "app.main:app",
                "--host",
                "127.0.0.1",
                "--port",
                str(api_port),
            ],
            cwd=ROOT / "backend",
            env=environment,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.STDOUT,
        )
        wait_for_backend(api_url, backend_process)
        imported = httpx.post(
            f"{api_url}/api/imports/amazon-html",
            json={
                "source_url": f"https://amazon.com.mx/dp/{selected_asin}",
                "html": html,
                "target_site_id": "MLM",
                "persist": True,
            },
            timeout=15,
        )
        imported.raise_for_status()
        draft_id = int(imported.json()["id"])
        session_factory = sessionmaker(bind=create_engine(database_url, pool_pre_ping=True))
        with session_factory() as db:
            draft = db.get(ProductDraft, draft_id)
            assert draft is not None and draft.source_product_id is not None
            source_id = draft.source_product_id

        endpoint = (
            f"{api_url}/api/imports/source-products/{source_id}/variants/"
            f"{variant_asin}/collection-job"
        )
        first = httpx.post(endpoint, json={"target_site_id": "MLB"}, timeout=15)
        first.raise_for_status()
        repeated = httpx.post(
            endpoint.replace(variant_asin, variant_asin.lower()),
            json={"target_site_id": "MLB"},
            timeout=15,
        )
        repeated.raise_for_status()
        job = first.json()
        job_id = int(job["id"])
        assert job["source_url"] == f"https://amazon.com.mx/dp/{variant_asin}"
        assert job["target_site_id"] == "MLB"
        assert job["status"] == "pending"
        assert repeated.json()["id"] == job_id
        with session_factory() as db:
            assert db.query(CollectionJob).filter(CollectionJob.id == job_id).count() == 1
        print(
            {
                "isolated_database": database_name,
                "variant_asin": variant_asin,
                "collection_job_id": job_id,
                "deduplicated": True,
                "production_rows_touched": 0,
            }
        )
    finally:
        stop_process(backend_process)
        if database_created:
            drop_isolated_database(ADMIN_DATABASE_URL, database_name)


if __name__ == "__main__":
    main()
