from fastapi import APIRouter, HTTPException, Query

from app.core.config import get_settings
from app.services.meli.oauth import (
    MercadoLibreOAuthClient,
    build_authorization_url,
    create_state_token,
)

router = APIRouter(prefix="/api/stores", tags=["stores"])
settings = get_settings()


def create_oauth_client() -> MercadoLibreOAuthClient:
    return MercadoLibreOAuthClient(
        client_id=settings.meli_client_id,
        client_secret=settings.meli_client_secret,
        redirect_uri=settings.meli_redirect_uri,
    )


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
async def meli_callback(code: str = Query(...), state: str = Query("")) -> dict[str, str]:
    token = await create_oauth_client().exchange_code(code)
    return {
        "status": "authorized",
        "seller_id": str(token.user_id),
        "state": state,
        "token_reference": f"meli:{token.user_id}",
    }
