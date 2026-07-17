from fastapi import FastAPI
from fastapi import Depends
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.routes import audit_events, drafts, imports, metadata, publishing, reviews, stores
from app.core.config import get_settings
from app.db.session import get_db
from app.models.collection_job import CollectionJob
from app.models.product_draft import ProductDraft
from app.models.publish_job import PublishJob
from app.models.store import Store
from app.models.registry import import_all_models


settings = get_settings()
import_all_models()


app = FastAPI(title=settings.app_name)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://127.0.0.1:5173", "http://localhost:5173"],
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


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": settings.app_name}


@app.get("/api/system/readiness")
def system_readiness(db: Session = Depends(get_db)) -> dict[str, object]:
    def count(model: type) -> int:
        return int(db.scalar(select(func.count()).select_from(model)) or 0)

    return {
        "database": True,
        "amazon_collector": True,
        "mercado_libre": {
            "credentials_configured": bool(
                settings.meli_client_id and settings.meli_client_secret
            ),
            "connected_stores": count(Store),
            "live_publish_enabled": settings.allow_live_publish,
        },
        "ai": {
            "claude_configured": bool(settings.claude_api_key),
            "nvidia_configured": bool(settings.nvidia_api_key),
        },
        "counts": {
            "drafts": count(ProductDraft),
            "collection_jobs": count(CollectionJob),
            "publish_jobs": count(PublishJob),
        },
    }
