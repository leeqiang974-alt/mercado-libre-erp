import httpx
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.session import get_db
from app.models.store import Store
from app.services.meli.client import MercadoLibreClient
from app.services.meli.oauth import (
    MercadoLibreOAuthClient,
    build_authorization_url,
    create_state_token,
)
from app.services.meli.token_vault import upsert_store_token

router = APIRouter(prefix="/api/stores", tags=["stores"])
settings = get_settings()


def create_oauth_client() -> MercadoLibreOAuthClient:
    return MercadoLibreOAuthClient(
        client_id=settings.meli_client_id,
        client_secret=settings.meli_client_secret,
        redirect_uri=settings.meli_redirect_uri,
    )


def create_meli_client(access_token: str) -> MercadoLibreClient:
    return MercadoLibreClient(access_token=access_token)


@router.get("/meli/authorization-url")
def get_meli_authorization_url() -> dict[str, str]:
    if not settings.meli_client_id:
        raise HTTPException(status_code=400, detail="MELI_CLIENT_ID is not configured.")
    state = create_state_token()
    return {
        "authorization_url": build_authorization_url(
            client_id=settings.meli_client_id,
            redirect_uri=settings.meli_redirect_uri,
            state=state,
        ),
        "state": state,
    }


@router.get("/meli/callback")
async def meli_callback(
    code: str = Query(...), state: str = Query(""), db: Session = Depends(get_db)
) -> dict[str, str]:
    token = await create_oauth_client().exchange_code(code)
    seller_id = str(token.user_id)
    try:
        profile = await create_meli_client(token.access_token).get("/users/me")
    except httpx.HTTPError as exc:
        raise HTTPException(
            status_code=502,
            detail="Mercado Libre authorization succeeded but seller site lookup failed.",
        ) from exc
    site_id = str(profile.get("site_id", "")).strip().upper()
    if not site_id:
        raise HTTPException(
            status_code=502,
            detail="Mercado Libre seller profile did not include a site_id.",
        )
    existing = db.query(Store).filter(Store.seller_id == seller_id).one_or_none()
    if existing:
        existing.site_id = site_id
        existing.oauth_status = "connected"
        existing.display_name = f"Mercado Libre {seller_id}"
        store = existing
    else:
        store = Store(
            site_id=site_id,
            seller_id=seller_id,
            display_name=f"Mercado Libre {seller_id}",
            oauth_status="connected",
        )
        db.add(store)
        db.flush()
    token_reference = upsert_store_token(
        db=db,
        store=store,
        token=token,
        encryption_key=settings.token_encryption_key,
    )
    db.commit()
    return {
        "status": "authorized",
        "seller_id": seller_id,
        "state": state,
        "token_reference": token_reference,
    }


@router.get("")
def list_stores(db: Session = Depends(get_db)) -> list[dict[str, str]]:
    return [
        {
            "id": str(store.id),
            "site_id": store.site_id,
            "seller_id": store.seller_id,
            "display_name": store.display_name,
            "oauth_status": store.oauth_status,
            "token_reference": store.token_reference,
        }
        for store in db.query(Store).order_by(Store.id.desc()).all()
    ]
