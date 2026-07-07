from fastapi import FastAPI

from app.api.routes import imports, publishing, reviews
from app.core.config import get_settings


settings = get_settings()
app = FastAPI(title=settings.app_name)
app.include_router(imports.router)
app.include_router(reviews.router)
app.include_router(publishing.router)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": settings.app_name}
