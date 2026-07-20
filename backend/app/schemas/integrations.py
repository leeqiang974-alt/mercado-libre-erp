from pydantic import BaseModel, SecretStr


class IntegrationCredentialsUpdate(BaseModel):
    meli_client_id: SecretStr | None = None
    meli_client_secret: SecretStr | None = None
    claude_api_key: SecretStr | None = None
    nvidia_api_key: SecretStr | None = None


class IntegrationCredentialStatus(BaseModel):
    meli_client_id_configured: bool
    meli_client_secret_configured: bool
    claude_api_key_configured: bool
    nvidia_api_key_configured: bool
    claude_model: str
    nvidia_model: str
    meli_redirect_uri: str
