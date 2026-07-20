import asyncio
from datetime import UTC, datetime
from time import perf_counter

import httpx
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.models.store import Store
from app.schemas.integrations import (
    IntegrationDiagnosticResult,
    IntegrationDiagnosticsResponse,
)
from app.services.audit_events import create_audit_event
from app.services.integration_credentials import resolve_integration_credentials
from app.services.meli.client import MercadoLibreClient
from app.services.meli.oauth import MercadoLibreOAuthClient
from app.services.meli.token_vault import resolve_fresh_store_access_token


CLAUDE_MODELS_URL = "https://api.anthropic.com/v1/models"
NVIDIA_MODELS_URL = "https://integrate.api.nvidia.com/v1/models"


async def run_integration_diagnostics(
    db: Session,
    settings: Settings,
    *,
    transport: httpx.AsyncBaseTransport | None = None,
) -> IntegrationDiagnosticsResponse:
    credentials = resolve_integration_credentials(db, settings)
    claude_task = _diagnose_model_provider(
        provider="claude",
        api_key=credentials.claude_api_key,
        model=settings.claude_model,
        url=CLAUDE_MODELS_URL,
        headers={
            "x-api-key": credentials.claude_api_key,
            "anthropic-version": "2023-06-01",
        },
        paginate_anthropic=True,
        transport=transport,
    )
    nvidia_task = _diagnose_model_provider(
        provider="nvidia",
        api_key=credentials.nvidia_api_key,
        model=settings.nvidia_model,
        url=NVIDIA_MODELS_URL,
        headers={"Authorization": f"Bearer {credentials.nvidia_api_key}"},
        paginate_anthropic=False,
        transport=transport,
    )
    claude, nvidia = await asyncio.gather(claude_task, nvidia_task)
    stores = db.query(Store).order_by(Store.id).all()
    has_connected_store = any(store.oauth_status == "connected" for store in stores)
    store_results = []
    for store in stores:
        store_results.append(
            await _diagnose_meli_store(
                db,
                settings,
                store,
                credentials.meli_client_id,
                credentials.meli_client_secret,
                transport=transport,
            )
        )
    meli_app = _meli_application_status(
        bool(credentials.meli_client_id),
        bool(credentials.meli_client_secret),
        has_connected_store=has_connected_store,
        has_verified_store=any(result.status == "verified" for result in store_results),
    )
    response = IntegrationDiagnosticsResponse(
        checked_at=datetime.now(UTC),
        results=[meli_app, claude, nvidia, *store_results],
    )
    create_audit_event(
        db=db,
        actor_type="operator",
        actor_id="local-ui",
        action="integrations.diagnostics.completed",
        entity_type="integration_credentials",
        entity_id="runtime",
        after={
            "results": [
                {
                    "provider": result.provider,
                    "subject": result.subject,
                    "status": result.status,
                    "code": result.code,
                    "model": result.model,
                    "store_id": result.store_id,
                    "duration_ms": result.duration_ms,
                }
                for result in response.results
            ]
        },
    )
    return response


async def _diagnose_model_provider(
    *,
    provider: str,
    api_key: str,
    model: str,
    url: str,
    headers: dict[str, str],
    paginate_anthropic: bool,
    transport: httpx.AsyncBaseTransport | None,
) -> IntegrationDiagnosticResult:
    if not api_key:
        return _result(provider, provider, "not_configured", "api_key_required", model=model)
    started = perf_counter()
    try:
        async with httpx.AsyncClient(transport=transport, timeout=20) as client:
            cursor = ""
            seen_cursors: set[str] = set()
            for _ in range(20):
                params = {"limit": "100"} if paginate_anthropic else {}
                if cursor:
                    params["after_id"] = cursor
                response = await client.get(
                    url,
                    headers={**headers, "Accept": "application/json"},
                    params=params,
                )
                response.raise_for_status()
                payload = response.json()
                if not isinstance(payload, dict) or not isinstance(payload.get("data"), list):
                    raise ValueError("models response is not an object with a data list")
                model_ids = {
                    str(item.get("id", "")).strip()
                    for item in payload["data"]
                    if isinstance(item, dict)
                }
                if model in model_ids:
                    return _result(
                        provider,
                        provider,
                        "verified",
                        "credentials_valid_model_available",
                        model=model,
                        started=started,
                    )
                if not paginate_anthropic or payload.get("has_more") is not True:
                    return _result(
                        provider,
                        provider,
                        "model_unavailable",
                        "configured_model_not_available",
                        model=model,
                        started=started,
                    )
                next_cursor = str(payload.get("last_id", "")).strip()
                if not next_cursor or next_cursor in seen_cursors:
                    raise ValueError("models pagination cursor is missing or repeated")
                seen_cursors.add(next_cursor)
                cursor = next_cursor
            raise ValueError("models pagination exceeded the page limit")
    except (ValueError, TypeError):
        return _result(
            provider,
            provider,
            "invalid_response",
            "models_response_invalid",
            model=model,
            started=started,
        )
    except httpx.HTTPError as exc:
        status, code = _http_failure(exc)
        return _result(provider, provider, status, code, model=model, started=started)


def _meli_application_status(
    client_id_configured: bool,
    client_secret_configured: bool,
    *,
    has_connected_store: bool,
    has_verified_store: bool,
) -> IntegrationDiagnosticResult:
    if not client_id_configured and not client_secret_configured:
        return _result(
            "mercado_libre", "application", "not_configured", "app_credentials_required"
        )
    if not client_id_configured or not client_secret_configured:
        return _result(
            "mercado_libre",
            "application",
            "not_configured",
            "app_credentials_incomplete",
        )
    if has_verified_store:
        return _result(
            "mercado_libre", "application", "configured", "authorized_store_available"
        )
    if has_connected_store:
        return _result(
            "mercado_libre",
            "application",
            "authorization_required",
            "connected_store_verification_failed",
        )
    return _result(
        "mercado_libre",
        "application",
        "authorization_required",
        "oauth_authorization_required",
    )


async def _diagnose_meli_store(
    db: Session,
    settings: Settings,
    store: Store,
    client_id: str,
    client_secret: str,
    *,
    transport: httpx.AsyncBaseTransport | None,
) -> IntegrationDiagnosticResult:
    subject = f"store:{store.id}"
    if store.oauth_status != "connected":
        return _result(
            "mercado_libre",
            subject,
            "authorization_required",
            "store_not_connected",
            store_id=store.id,
        )
    started = perf_counter()
    try:
        access_token = await resolve_fresh_store_access_token(
            db=db,
            store=store,
            encryption_key=settings.token_encryption_key,
            oauth_client=MercadoLibreOAuthClient(
                client_id=client_id,
                client_secret=client_secret,
                redirect_uri=settings.meli_redirect_uri,
                transport=transport,
            ),
        )
    except (ValueError, TypeError):
        db.rollback()
        return _result(
            "mercado_libre",
            subject,
            "invalid_response",
            "token_refresh_response_invalid",
            store_id=store.id,
            started=started,
        )
    except httpx.HTTPError as exc:
        db.rollback()
        if isinstance(exc, httpx.HTTPStatusError) and exc.response.status_code == 400:
            return _result(
                "mercado_libre",
                subject,
                "authorization_required",
                "store_reauthorization_required",
                store_id=store.id,
                started=started,
            )
        status, code = _http_failure(exc)
        return _result(
            "mercado_libre",
            subject,
            status,
            code,
            store_id=store.id,
            started=started,
        )
    if not access_token:
        db.rollback()
        return _result(
            "mercado_libre",
            subject,
            "authorization_required",
            "store_token_unavailable",
            store_id=store.id,
            started=started,
        )
    try:
        profile = await MercadoLibreClient(
            access_token=access_token,
            transport=transport,
            timeout=20,
        ).get("/users/me")
        if not isinstance(profile, dict):
            raise ValueError("seller profile must be an object")
        seller_id = str(profile.get("id", "")).strip()
        site_id = str(profile.get("site_id", "")).strip().upper()
        if seller_id != str(store.seller_id) or site_id != store.site_id.strip().upper():
            return _result(
                "mercado_libre",
                subject,
                "invalid_response",
                "store_identity_mismatch",
                store_id=store.id,
                started=started,
            )
        return _result(
            "mercado_libre",
            subject,
            "verified",
            "store_identity_verified",
            store_id=store.id,
            started=started,
        )
    except (ValueError, TypeError):
        return _result(
            "mercado_libre",
            subject,
            "invalid_response",
            "seller_profile_invalid",
            store_id=store.id,
            started=started,
        )
    except httpx.HTTPError as exc:
        status, code = _http_failure(exc)
        return _result(
            "mercado_libre",
            subject,
            status,
            code,
            store_id=store.id,
            started=started,
        )


def _http_failure(exc: httpx.HTTPError) -> tuple[str, str]:
    if isinstance(exc, httpx.HTTPStatusError):
        status_code = exc.response.status_code
        if status_code == 401:
            return "authentication_failed", "provider_authentication_failed"
        if status_code == 403:
            return "permission_denied", "provider_permission_denied"
        if status_code == 429:
            return "rate_limited", "provider_rate_limited"
        if status_code == 402:
            return "payment_required", "provider_payment_required"
        if 400 <= status_code < 500:
            return "request_rejected", "provider_request_rejected"
    return "unreachable", "provider_unavailable"


def _result(
    provider: str,
    subject: str,
    status: str,
    code: str,
    *,
    model: str = "",
    store_id: int | None = None,
    started: float | None = None,
) -> IntegrationDiagnosticResult:
    duration_ms = max(0, round((perf_counter() - started) * 1000)) if started else 0
    return IntegrationDiagnosticResult(
        provider=provider,
        subject=subject,
        status=status,
        code=code,
        model=model,
        store_id=store_id,
        duration_ms=duration_ms,
    )
