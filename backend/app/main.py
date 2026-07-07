from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import drafts, imports, metadata, publishing, reviews, stores
from app.core.config import get_settings
from app.db.base import Base
from app.db.session import engine
from app.models.registry import import_all_models


settings = get_settings()
import_all_models()


@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(bind=engine)
    yield


app = FastAPI(title=settings.app_name, lifespan=lifespan)
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


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": settings.app_name}
