from typing import Annotated
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, Header, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.session import get_db
from app.schemas.integrations import (
    IntegrationCredentialStatus,
    IntegrationCredentialsUpdate,
    IntegrationDiagnosticsResponse,
)
from app.schemas.provider_pricing import ProviderModelPriceCreate, ProviderModelPriceRead
from app.services.integration_diagnostics import run_integration_diagnostics
from app.services.integration_credentials import (
    integration_credential_status,
    update_integration_credentials,
)
from app.services.provider_pricing import (
    deactivate_provider_model_price,
    list_provider_model_prices,
    save_provider_model_price,
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


@router.post("/diagnostics", response_model=IntegrationDiagnosticsResponse)
async def diagnose_integrations(
    db: Session = Depends(get_db),
) -> IntegrationDiagnosticsResponse:
    return await run_integration_diagnostics(db, settings)


@router.get("/model-prices", response_model=list[ProviderModelPriceRead])
def get_model_prices(
    include_history: bool = Query(default=False), db: Session = Depends(get_db)
) -> list[ProviderModelPriceRead]:
    return list_provider_model_prices(db, include_history=include_history)


@router.put("/model-prices", response_model=ProviderModelPriceRead)
def put_model_price(
    payload: ProviderModelPriceCreate, db: Session = Depends(get_db)
) -> ProviderModelPriceRead:
    return ProviderModelPriceRead.model_validate(
        save_provider_model_price(db, payload), from_attributes=True
    )


@router.delete("/model-prices/{price_id}", response_model=ProviderModelPriceRead)
def delete_model_price(
    price_id: int, db: Session = Depends(get_db)
) -> ProviderModelPriceRead:
    return ProviderModelPriceRead.model_validate(
        deactivate_provider_model_price(db, price_id), from_attributes=True
    )
