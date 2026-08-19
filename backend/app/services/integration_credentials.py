from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy.orm import Session

from app.core.config import Settings
from app.models.integration_credential import IntegrationCredential
from app.schemas.integrations import IntegrationCredentialStatus, IntegrationCredentialsUpdate
from app.services.audit_events import create_audit_event
from app.services.meli.token_vault import decrypt_token_value, encrypt_token_value


CREDENTIAL_KEYS = (
    "meli_client_id",
    "meli_client_secret",
    "claude_api_key",
    "nvidia_api_key",
    "volcengine_api_key",
)


@dataclass(frozen=True)
class ResolvedIntegrationCredentials:
    meli_client_id: str
    meli_client_secret: str
    claude_api_key: str
    nvidia_api_key: str
    volcengine_api_key: str = ""


def resolve_integration_credentials(
    db: Session, settings: Settings
) -> ResolvedIntegrationCredentials:
    rows = {
        row.credential_key: row
        for row in db.query(IntegrationCredential)
        .filter(IntegrationCredential.credential_key.in_(CREDENTIAL_KEYS))
        .all()
    }

    def resolve(key: str) -> str:
        row = rows.get(key)
        if row is None:
            return str(getattr(settings, key, "") or "").strip()
        return decrypt_token_value(row.encrypted_value, settings.token_encryption_key).strip()

    return ResolvedIntegrationCredentials(**{key: resolve(key) for key in CREDENTIAL_KEYS})


def integration_credential_status(
    db: Session, settings: Settings
) -> IntegrationCredentialStatus:
    resolved = resolve_integration_credentials(db, settings)
    return IntegrationCredentialStatus(
        meli_client_id_configured=bool(resolved.meli_client_id),
        meli_client_secret_configured=bool(resolved.meli_client_secret),
        claude_api_key_configured=bool(resolved.claude_api_key),
        nvidia_api_key_configured=bool(resolved.nvidia_api_key),
        volcengine_api_key_configured=bool(resolved.volcengine_api_key),
        claude_model=settings.claude_model,
        nvidia_model=settings.nvidia_model,
        volcengine_model=settings.volcengine_model,
        meli_redirect_uri=settings.meli_redirect_uri,
    )


def update_integration_credentials(
    db: Session,
    payload: IntegrationCredentialsUpdate,
    settings: Settings,
    operation_id: str,
) -> IntegrationCredentialStatus:
    updates = payload.model_dump(exclude_unset=True)
    changed_keys: list[str] = []
    for key, raw_value in updates.items():
        if key not in CREDENTIAL_KEYS or raw_value is None:
            continue
        value = raw_value.get_secret_value().strip()
        row = (
            db.query(IntegrationCredential)
            .filter(IntegrationCredential.credential_key == key)
            .one_or_none()
        )
        if row is None:
            row = IntegrationCredential(credential_key=key, encrypted_value="")
            db.add(row)
        row.encrypted_value = encrypt_token_value(value, settings.token_encryption_key)
        row.last_operation_id = operation_id
        row.updated_at = datetime.now(UTC)
        changed_keys.append(key)
    if changed_keys:
        create_audit_event(
            db=db,
            actor_type="operator",
            actor_id="local-ui",
            action="integrations.credentials.updated",
            entity_type="integration_credentials",
            entity_id="runtime",
            after={"changed_keys": changed_keys, "operation_id": operation_id},
            commit=False,
        )
    db.commit()
    return integration_credential_status(db, settings)
