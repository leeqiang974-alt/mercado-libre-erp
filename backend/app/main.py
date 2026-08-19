from fastapi import FastAPI
from fastapi import Depends
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import func, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.api.routes import (
    audit_events,
    drafts,
    erp,
    imports,
    integrations,
    metadata,
    publishing,
    reviews,
    stores,
)
from app.core.config import get_settings
from app.core.request_limits import RequestBodyLimitMiddleware
from app.db.session import get_db
from app.models.collection_job import CollectionJob
from app.models.product_draft import ProductDraft
from app.models.publish_job import PublishJob
from app.models.store import Store
from app.models.registry import import_all_models
from app.services.integration_credentials import integration_credential_status
from app.services.amazon.import_file import MAX_IMPORT_REQUEST_BYTES


settings = get_settings()
import_all_models()


app = FastAPI(title=settings.app_name)
app.add_middleware(
    RequestBodyLimitMiddleware,
    path_limits={"/api/imports/amazon-url/jobs/file": MAX_IMPORT_REQUEST_BYTES},
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        settings.frontend_url,
        "http://127.0.0.1:5173",
        "http://localhost:5173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(imports.router)
app.include_router(drafts.router)
app.include_router(metadata.router)
app.include_router(reviews.router)
app.include_router(publishing.router)
app.include_router(stores.router)
app.include_router(audit_events.router)
app.include_router(integrations.router)
app.include_router(erp.router)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": settings.app_name}


@app.get("/api/system/readiness")
def system_readiness(db: Session = Depends(get_db)) -> dict[str, object]:
    def count(model: type) -> int:
        return int(db.scalar(select(func.count()).select_from(model)) or 0)

    database_ready = True
    counts = {"stores": 0, "drafts": 0, "collection_jobs": 0, "publish_jobs": 0}
    credential_status = None
    try:
        counts = {
            "stores": count(Store),
            "drafts": count(ProductDraft),
            "collection_jobs": count(CollectionJob),
            "publish_jobs": count(PublishJob),
        }
        credential_status = integration_credential_status(db, settings)
    except SQLAlchemyError:
        db.rollback()
        database_ready = False

    return {
        "database": database_ready,
        "amazon_collector": True,
        "mercado_libre": {
            "credentials_configured": bool(
                credential_status
                and credential_status.meli_client_id_configured
                and credential_status.meli_client_secret_configured
            ),
            "connected_stores": counts["stores"],
            "live_publish_enabled": settings.allow_live_publish,
        },
        "ai": {
            "claude_configured": bool(
                credential_status and credential_status.claude_api_key_configured
            ),
            "nvidia_configured": bool(
                credential_status and credential_status.nvidia_api_key_configured
            ),
        },
        "counts": {
            "drafts": counts["drafts"],
            "collection_jobs": counts["collection_jobs"],
            "publish_jobs": counts["publish_jobs"],
        },
    }
