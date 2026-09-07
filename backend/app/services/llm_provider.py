"""LLM provider 注册表与当前选择存取。

添加新模型：只需在 list_llm_providers 的列表中新增一项
（id/name/model/base_url/key 来源），前端会自动渲染出新的选项。
当前选择持久化在 integration_credentials.content_generation_provider，
生成内容时 DB 优先、环境变量兜底。
"""
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.models.integration_credential import IntegrationCredential
from app.services.meli.token_vault import decrypt_token_value, encrypt_token_value

PROVIDER_KEY = "content_generation_provider"
VALID_PROVIDERS = ("deepseek", "volcengine", "agnes")


def list_llm_providers(settings: Settings) -> list[dict]:
    """模型清单（配置驱动，前端自动渲染）。"""
    return [
        {
            "id": "deepseek",
            "name": "DeepSeek",
            "model": settings.deepseek_model,
            "base_url": settings.deepseek_base_url,
            "key_configured": bool(settings.deepseek_api_key),
        },
        {
            "id": "volcengine",
            "name": "火山引擎（方舟）",
            "model": settings.volcengine_model,
            "base_url": settings.volcengine_base_url,
            "key_configured": bool(settings.volcengine_api_key),
        },
        {
            "id": "agnes",
            "name": "Agnes",
            "model": settings.agnes_model,
            "base_url": settings.agnes_base_url,
            "key_configured": bool(settings.agnes_api_key),
        },
    ]


def _is_valid(provider: str) -> bool:
    return provider in VALID_PROVIDERS


def get_current_provider(db: Session, settings: Settings) -> str:
    """当前生效的 provider：DB 持久化值优先，异常/缺失回退环境变量默认。"""
    row = (
        db.query(IntegrationCredential)
        .filter(IntegrationCredential.credential_key == PROVIDER_KEY)
        .one_or_none()
    )
    if row is not None and row.encrypted_value:
        try:
            value = decrypt_token_value(row.encrypted_value, settings.token_encryption_key).strip()
            if _is_valid(value):
                return value
        except Exception:
            pass
    fallback = settings.content_generation_provider
    return fallback if _is_valid(fallback) else "deepseek"


def set_current_provider(db: Session, settings: Settings, provider: str) -> str:
    """持久化切换 provider；非法值抛 ValueError。"""
    provider = provider.strip().lower()
    if not _is_valid(provider):
        raise ValueError(f"unknown provider: {provider}")
    row = (
        db.query(IntegrationCredential)
        .filter(IntegrationCredential.credential_key == PROVIDER_KEY)
        .one_or_none()
    )
    if row is None:
        row = IntegrationCredential(credential_key=PROVIDER_KEY, encrypted_value="")
        db.add(row)
    row.encrypted_value = encrypt_token_value(provider, settings.token_encryption_key)
    db.commit()
    return provider
