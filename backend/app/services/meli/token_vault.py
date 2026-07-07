import base64
import hashlib
from datetime import UTC, datetime, timedelta

from cryptography.fernet import Fernet, InvalidToken
from sqlalchemy.orm import Session

from app.models.store import Store
from app.models.token_credential import TokenCredential
from app.services.meli.oauth import MercadoLibreOAuthClient, MercadoLibreToken


def encrypt_token_value(value: str, encryption_key: str) -> str:
    return _fernet(encryption_key).encrypt(value.encode("utf-8")).decode("utf-8")


def decrypt_token_value(value: str, encryption_key: str) -> str:
    try:
        return _fernet(encryption_key).decrypt(value.encode("utf-8")).decode("utf-8")
    except InvalidToken:
        return ""


def upsert_store_token(
    db: Session,
    store: Store,
    token: MercadoLibreToken,
    encryption_key: str,
) -> str:
    token_reference = f"meli:{store.seller_id}"
    expires_at = datetime.now(UTC) + timedelta(seconds=token.expires_in)
    credential = (
        db.query(TokenCredential)
        .filter(TokenCredential.token_reference == token_reference)
        .one_or_none()
    )
    if credential is None:
        credential = TokenCredential(
            store_id=store.id,
            token_reference=token_reference,
            encrypted_access_token="",
            encrypted_refresh_token="",
        )
        db.add(credential)

    credential.store_id = store.id
    credential.encrypted_access_token = encrypt_token_value(token.access_token, encryption_key)
    credential.encrypted_refresh_token = encrypt_token_value(token.refresh_token, encryption_key)
    credential.expires_at = expires_at
    credential.updated_at = datetime.now(UTC)
    store.token_reference = token_reference
    return token_reference


def resolve_store_access_token(db: Session, store: Store, encryption_key: str) -> str:
    credential = get_store_credential(db, store)
    if credential is None:
        return ""
    return decrypt_token_value(credential.encrypted_access_token, encryption_key)


async def resolve_fresh_store_access_token(
    db: Session,
    store: Store,
    encryption_key: str,
    oauth_client: MercadoLibreOAuthClient,
    refresh_window_seconds: int = 300,
) -> str:
    credential = get_store_credential(db, store)
    if credential is None:
        return ""
    if not _needs_refresh(credential, refresh_window_seconds):
        return decrypt_token_value(credential.encrypted_access_token, encryption_key)

    refresh_token = decrypt_token_value(credential.encrypted_refresh_token, encryption_key)
    if not refresh_token:
        return ""
    token = await oauth_client.refresh_token(refresh_token)
    upsert_store_token(db, store, token, encryption_key)
    db.commit()
    return token.access_token


def get_store_credential(db: Session, store: Store) -> TokenCredential | None:
    if not store.token_reference:
        return None
    return (
        db.query(TokenCredential)
        .filter(
            TokenCredential.store_id == store.id,
            TokenCredential.token_reference == store.token_reference,
        )
        .one_or_none()
    )


def _needs_refresh(credential: TokenCredential, refresh_window_seconds: int) -> bool:
    if credential.expires_at is None:
        return False
    expires_at = credential.expires_at
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=UTC)
    return expires_at <= datetime.now(UTC) + timedelta(seconds=refresh_window_seconds)


def _fernet(encryption_key: str) -> Fernet:
    key = encryption_key.encode("utf-8")
    try:
        return Fernet(key)
    except ValueError:
        digest = hashlib.sha256(key).digest()
        return Fernet(base64.urlsafe_b64encode(digest))
