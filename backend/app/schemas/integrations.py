from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, SecretStr


class IntegrationCredentialsUpdate(BaseModel):
    meli_client_id: SecretStr | None = None
    meli_client_secret: SecretStr | None = None
    claude_api_key: SecretStr | None = None
    nvidia_api_key: SecretStr | None = None
    volcengine_api_key: SecretStr | None = None


class IntegrationCredentialStatus(BaseModel):
    meli_client_id_configured: bool
    meli_client_secret_configured: bool
    claude_api_key_configured: bool
    nvidia_api_key_configured: bool
    volcengine_api_key_configured: bool
    claude_model: str
    nvidia_model: str
    volcengine_model: str
    meli_redirect_uri: str


class IntegrationDiagnosticResult(BaseModel):
    provider: Literal["mercado_libre", "claude", "nvidia"]
    subject: str
    status: Literal[
        "not_configured",
        "configured",
        "authorization_required",
        "verified",
        "authentication_failed",
        "permission_denied",
        "payment_required",
        "request_rejected",
        "rate_limited",
        "model_unavailable",
        "unreachable",
        "invalid_response",
    ]
    code: str
    model: str = ""
    store_id: int | None = None
    duration_ms: int = 0


class IntegrationDiagnosticsResponse(BaseModel):
    checked_at: datetime
    results: list[IntegrationDiagnosticResult] = Field(default_factory=list)
