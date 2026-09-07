"""LLM 模型选择：列出可用模型、读取/切换当前内容生成模型。"""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.session import get_db
from app.services.llm_provider import (
    get_current_provider,
    list_llm_providers,
    set_current_provider,
)

router = APIRouter(prefix="/api/llm", tags=["llm"])

settings = get_settings()


class ProviderSwitch(BaseModel):
    provider: str


@router.get("/providers")
def providers(db: Session = Depends(get_db)) -> dict:
    """可用模型清单 + 当前选择。"""
    return {
        "providers": list_llm_providers(settings),
        "current": get_current_provider(db, settings),
    }


@router.get("/current")
def current(db: Session = Depends(get_db)) -> dict:
    return {"provider": get_current_provider(db, settings)}


@router.post("/current")
def switch(payload: ProviderSwitch, db: Session = Depends(get_db)) -> dict:
    try:
        provider = set_current_provider(db, settings, payload.provider)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return {"provider": provider}
