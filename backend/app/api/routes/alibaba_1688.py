"""1688 OAuth authorization for the cross-border image-search integration.

Credentials and returned access tokens stay server-side.  The browser only
receives the authorization redirect and a final success/failure message.
"""

import base64
import hashlib
import hmac
import json
import secrets
import time
from urllib.parse import urlencode

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.session import get_db
from app.models.integration_credential import IntegrationCredential
from app.models.product_draft import ProductDraft
from app.services.meli.token_vault import decrypt_token_value, encrypt_token_value
from app.services.storage.aliyun_oss import OssMirrorError, mirror_image_to_oss


router = APIRouter(prefix="/api/integrations/1688", tags=["1688"])
settings = get_settings()
AUTH_URL = "https://auth.1688.com/oauth/authorize"
TOKEN_URL = "https://gw.open.1688.com/openapi/param2/1/system.oauth2/getToken/{app_key}"
TOKEN_KEY = "alibaba_1688_access_token"
SIMILAR_API = "com.alibaba.linkplus/alibaba.cross.similar.offer.search"


def _state() -> str:
    payload = {"exp": int(time.time()) + 600, "nonce": secrets.token_urlsafe(18)}
    encoded = base64.urlsafe_b64encode(json.dumps(payload, separators=(",", ":")).encode()).decode().rstrip("=")
    signature = hmac.new(settings.token_encryption_key.encode(), encoded.encode(), hashlib.sha256).hexdigest()
    return f"{encoded}.{signature}"


def _valid_state(value: str) -> bool:
    try:
        encoded, signature = value.rsplit(".", 1)
        expected = hmac.new(settings.token_encryption_key.encode(), encoded.encode(), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(signature, expected):
            return False
        payload = json.loads(base64.urlsafe_b64decode(encoded + "=" * (-len(encoded) % 4)))
        return int(payload.get("exp", 0)) >= int(time.time())
    except (ValueError, TypeError, json.JSONDecodeError):
        return False


def _require_app_credentials() -> None:
    if not settings.alibaba_1688_app_key or not settings.alibaba_1688_app_secret:
        raise HTTPException(status_code=409, detail="1688_app_credentials_not_configured")


def _access_token(db: Session) -> str:
    row = db.query(IntegrationCredential).filter(IntegrationCredential.credential_key == TOKEN_KEY).one_or_none()
    if row is None or not row.encrypted_value:
        raise HTTPException(status_code=409, detail="1688_authorization_required")
    return decrypt_token_value(row.encrypted_value, settings.token_encryption_key).strip()


@router.get("/authorize")
def authorize_1688() -> RedirectResponse:
    """Open the official 1688 consent page; safe to share with the operator."""
    _require_app_credentials()
    query = urlencode({
        "client_id": settings.alibaba_1688_app_key,
        "site": "1688",
        "redirect_uri": settings.alibaba_1688_redirect_uri,
        "state": _state(),
    })
    return RedirectResponse(f"{AUTH_URL}?{query}", status_code=302)


@router.get("/callback")
async def callback_1688(
    code: str = Query(..., min_length=1),
    state: str = Query(..., min_length=1),
    db: Session = Depends(get_db),
) -> RedirectResponse:
    """Exchange the one-time code and encrypt the access token at rest."""
    _require_app_credentials()
    if not _valid_state(state):
        raise HTTPException(status_code=400, detail="invalid_or_expired_1688_oauth_state")
    form = {
        "grant_type": "authorization_code",
        "need_refresh_token": "true",
        "client_id": settings.alibaba_1688_app_key,
        "client_secret": settings.alibaba_1688_app_secret,
        "redirect_uri": settings.alibaba_1688_redirect_uri,
        "code": code,
    }
    try:
        async with httpx.AsyncClient(timeout=settings.api_request_timeout_seconds) as client:
            response = await client.post(TOKEN_URL.format(app_key=settings.alibaba_1688_app_key), data=form)
            response.raise_for_status()
            payload = response.json()
    except (httpx.HTTPError, ValueError) as exc:
        raise HTTPException(status_code=502, detail="1688_token_exchange_failed") from exc
    token = str(payload.get("access_token") or "").strip()
    if not token:
        raise HTTPException(status_code=502, detail="1688_token_exchange_returned_no_access_token")
    row = db.query(IntegrationCredential).filter(IntegrationCredential.credential_key == TOKEN_KEY).one_or_none()
    if row is None:
        row = IntegrationCredential(credential_key=TOKEN_KEY, encrypted_value="")
        db.add(row)
    row.encrypted_value = encrypt_token_value(token, settings.token_encryption_key)
    db.commit()
    return RedirectResponse(f"{settings.frontend_url.rstrip('/')}/#stores?alibaba_1688=authorized", status_code=303)


@router.get("/status")
def authorization_status(db: Session = Depends(get_db)) -> dict[str, bool]:
    row = db.query(IntegrationCredential).filter(IntegrationCredential.credential_key == TOKEN_KEY).one_or_none()
    return {
        "app_configured": bool(settings.alibaba_1688_app_key and settings.alibaba_1688_app_secret),
        "access_token_configured": bool(row and row.encrypted_value),
    }


@router.post("/drafts/{product_draft_id}/similar-offers")
async def search_similar_offers(product_draft_id: int, db: Session = Depends(get_db)) -> dict[str, object]:
    """Search by the selected draft cover image; no source image is downloaded."""
    _require_app_credentials()
    draft = db.get(ProductDraft, product_draft_id)
    if draft is None:
        raise HTTPException(status_code=404, detail="Product draft not found.")
    pictures = draft.image_urls_json or []
    if not pictures or not str(pictures[0]).startswith(("https://", "http://")):
        raise HTTPException(status_code=422, detail="draft_cover_image_required")
    try:
        # 1688 must fetch the image itself. Amazon CDN URLs can reject that
        # server-to-server request, so submit the already verified OSS copy.
        search_image = await mirror_image_to_oss(str(pictures[0]), settings)
    except OssMirrorError as exc:
        raise HTTPException(status_code=422, detail=f"1688_cover_image_prepare_failed: {exc}") from exc
    path = f"param2/1/{SIMILAR_API}/{settings.alibaba_1688_app_key}"
    params = {
        "access_token": _access_token(db),
        "_aop_timestamp": str(int(time.time() * 1000)),
        "picUrl": search_image,
        "page": "1",
    }
    signing_text = path + "".join(key + params[key] for key in sorted(params))
    params["_aop_signature"] = hmac.new(
        settings.alibaba_1688_app_secret.encode(), signing_text.encode(), hashlib.sha1,
    ).hexdigest().upper()
    try:
        async with httpx.AsyncClient(timeout=settings.api_request_timeout_seconds) as client:
            response = await client.post(f"https://gw.open.1688.com/openapi/{path}", data=params)
            response.raise_for_status()
            payload = response.json()
    except httpx.HTTPStatusError as exc:
        try:
            error_payload = exc.response.json()
        except ValueError:
            error_payload = {}
        error_code = str(error_payload.get("error_code") or error_payload.get("code") or "http_error")
        raise HTTPException(status_code=502, detail=f"1688_api_rejected:{exc.response.status_code}:{error_code}") from exc
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=502, detail="1688_similar_offer_search_unreachable") from exc
    except ValueError as exc:
        raise HTTPException(status_code=502, detail="1688_similar_offer_invalid_response") from exc
    if not isinstance(payload, dict) or payload.get("success") is not True:
        raise HTTPException(status_code=502, detail="1688_similar_offer_search_rejected")
    result = payload.get("result") if isinstance(payload.get("result"), dict) else {}
    rows = result.get("result") if isinstance(result.get("result"), list) else []
    offers = []
    for rank, item in enumerate(rows[:5], start=1):
        if not isinstance(item, dict):
            continue
        offers.append({
            "rank": rank,
            # The API returns relevance order but not a numerical similarity score.
            "match_level": "高匹配" if rank <= 2 else "参考匹配",
            "offer_id": str(item.get("offerId") or ""),
            "title": str(item.get("subject") or "未提供标题"),
            "price": item.get("price") if item.get("price") is not None else item.get("oldPrice"),
            "image_url": str(item.get("imageUrl") or ""),
            "supply_amount": item.get("supplyAmount"),
            "province": str(item.get("province") or ""),
            "city": str(item.get("city") or ""),
        })
    return {"draft_id": product_draft_id, "cover_image": str(pictures[0]), "total": result.get("total"), "offers": offers}
