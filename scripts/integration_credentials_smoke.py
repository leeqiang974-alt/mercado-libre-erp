import os
from pathlib import Path
import subprocess
import sys
from uuid import uuid4

import httpx
from playwright.sync_api import Route, sync_playwright
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "backend"))

from scripts.isolated_runtime import (  # noqa: E402
    available_port,
    build_isolated_database_url,
    create_isolated_database,
    drop_isolated_database,
    stop_process,
    wait_for_backend,
)

from app.models.audit_event import AuditEvent  # noqa: E402
from app.models.integration_credential import IntegrationCredential  # noqa: E402
from app.models.registry import import_all_models  # noqa: E402


ADMIN_DATABASE_URL = os.getenv(
    "INTEGRATION_CREDENTIAL_SMOKE_ADMIN_DATABASE_URL",
    "postgresql+psycopg://meli:meli@127.0.0.1:5432/amazon_meli",
)
APP_URL = os.getenv("INTEGRATION_CREDENTIAL_SMOKE_APP_URL", "http://127.0.0.1:5173")
CHROME = Path(r"C:\Program Files\Google\Chrome\Application\chrome.exe")
KEYS = ("meli_client_id", "meli_client_secret", "claude_api_key", "nvidia_api_key")


def main() -> None:
    import_all_models()
    database_name = f"integration_credentials_smoke_{uuid4().hex}"
    database_url = build_isolated_database_url(ADMIN_DATABASE_URL, database_name)
    api_port = available_port()
    api_url = f"http://127.0.0.1:{api_port}"
    backend_process: subprocess.Popen | None = None
    database_created = False
    secrets = {
        "meli_client_id": "smoke-meli-client",
        "meli_client_secret": "smoke-meli-secret",
        "claude_api_key": "smoke-claude-secret",
        "nvidia_api_key": "smoke-nvidia-secret",
    }
    operation_id = str(uuid4())
    environment = os.environ.copy()
    environment.update(
        {
            "DATABASE_URL": database_url,
            "TOKEN_ENCRYPTION_KEY": f"credential-smoke-{uuid4().hex}",
            "MELI_CLIENT_ID": "",
            "MELI_CLIENT_SECRET": "",
            "CLAUDE_API_KEY": "",
            "NVIDIA_API_KEY": "",
            "ALLOW_LIVE_PUBLISH": "false",
        }
    )
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
        response = httpx.put(
            f"{api_url}/api/integrations/credentials",
            json=secrets,
            headers={"X-Integration-Operation-ID": operation_id},
            timeout=15,
        )
        response.raise_for_status()
        assert all(secret not in response.text for secret in secrets.values())
        assert all(
            response.json()[key]
            for key in (
                "meli_client_id_configured",
                "meli_client_secret_configured",
                "claude_api_key_configured",
                "nvidia_api_key_configured",
            )
        )

        session_factory = sessionmaker(bind=create_engine(database_url, pool_pre_ping=True))
        with session_factory() as db:
            rows = db.scalars(
                select(IntegrationCredential).where(
                    IntegrationCredential.credential_key.in_(KEYS)
                )
            ).all()
            assert len(rows) == 4
            assert all(row.last_operation_id == operation_id for row in rows)
            assert all(secrets[row.credential_key] not in row.encrypted_value for row in rows)
            audit = db.scalars(
                select(AuditEvent).where(
                    AuditEvent.action == "integrations.credentials.updated"
                )
            ).one()
            assert (audit.after_json or {}).get("operation_id") == operation_id

        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True, executable_path=str(CHROME))
            page = browser.new_page(viewport={"width": 1280, "height": 900})

            def route_isolated_api(route: Route) -> None:
                route.continue_(url=route.request.url.replace("http://127.0.0.1:8000", api_url, 1))

            page.route("http://127.0.0.1:8000/**", route_isolated_api)
            page.goto(APP_URL, wait_until="domcontentloaded")
            page.get_by_role("button", name="Stores", exact=True).click()
            page.get_by_role("heading", name="Integration credentials", exact=True).wait_for()
            page.get_by_text("claude-sonnet-4-6", exact=True).wait_for()
            page.get_by_text("meta/llama-3.1-70b-instruct", exact=True).wait_for()
            body = page.locator("body").inner_text()
            assert all(secret not in body for secret in secrets.values())
            assert page.locator('.credential-provider-row input[type="password"]').count() == 4
            assert all(
                value == ""
                for value in page.locator(
                    '.credential-provider-row input[type="password"]'
                ).evaluate_all("elements => elements.map(element => element.value)")
            )
            browser.close()
        print(
            {
                "isolated_database": database_name,
                "encrypted_rows": 4,
                "ui_secret_values": 0,
                "production_rows_touched": 0,
            }
        )
    finally:
        stop_process(backend_process)
        if database_created:
            drop_isolated_database(ADMIN_DATABASE_URL, database_name)


if __name__ == "__main__":
    main()
