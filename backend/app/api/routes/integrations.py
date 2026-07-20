from typing import Annotated
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, Header, HTTPException
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.session import get_db
from app.schemas.integrations import IntegrationCredentialStatus, IntegrationCredentialsUpdate
from app.services.integration_credentials import (
    integration_credential_status,
    update_integration_credentials,
)


router = APIRouter(prefix="/api/integrations", tags=["integrations"])
settings = get_settings()


@router.get("/credentials", response_model=IntegrationCredentialStatus)
def get_credentials_status(db: Session = Depends(get_db)) -> IntegrationCredentialStatus:
    return integration_credential_status(db, settings)


@router.put("/credentials", response_model=IntegrationCredentialStatus)
def save_credentials(
    payload: IntegrationCredentialsUpdate,
    db: Session = Depends(get_db),
    requested_operation_id: Annotated[
        str | None, Header(alias="X-Integration-Operation-ID")
    ] = None,
) -> IntegrationCredentialStatus:
    try:
        operation_id = str(UUID(requested_operation_id)) if requested_operation_id else str(uuid4())
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Invalid integration operation ID.") from exc
    return update_integration_credentials(db, payload, settings, operation_id)
