from datetime import UTC, datetime
from email.utils import parsedate_to_datetime
import json
from typing import Literal

import httpx
from pydantic import BaseModel, ConfigDict

from app.schemas.reviews import ReviewResponse

REVIEW_PROMPT_VERSION = "meli-safety-v2"
BEHAVIORAL_AUDIT_PROMPT_VERSION = "meli-behavioral-audit-v2"


class ProviderReviewPayload(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    decision: Literal["pass", "needs_human_review", "block"]
    risk_level: Literal["low", "medium", "high"]
    reason_codes: list[str]
    reasons: list[str]
    suggested_changes: dict[str, object]


class AIProviderError(RuntimeError):
    def __init__(
        self,
        provider: str,
        code: str,
        *,
        http_status: int | None = None,
        retryable: bool = False,
        retry_after_seconds: int | None = None,
        request_id: str = "",
    ):
        self.provider = provider
        self.code = code
        self.http_status = http_status
        self.retryable = retryable
        self.retry_after_seconds = retry_after_seconds
        self.request_id = request_id
        super().__init__(f"{provider}:{code}")


def provider_request_error(provider: str, exc: Exception) -> AIProviderError:
    if isinstance(exc, httpx.HTTPStatusError):
        response = exc.response
        status = response.status_code
        if status == 429:
            code, retryable = "rate_limited", True
        elif status == 401:
            code, retryable = "authentication_failed", False
        elif status == 403:
            code, retryable = "permission_denied", False
        elif status == 402:
            code, retryable = "billing_required", False
        elif status in {408, 409, 425} or status >= 500:
            code, retryable = "provider_unavailable", True
        else:
            code, retryable = "request_rejected", False
        try:
            error_data = response.json()
        except (ValueError, TypeError):
            error_data = None
        return AIProviderError(
            provider,
            code,
            http_status=status,
            retryable=retryable,
            retry_after_seconds=_retry_after_seconds(response.headers.get("retry-after")),
            request_id=provider_request_id(
                response, error_data if isinstance(error_data, dict) else None
            ),
        )
    if isinstance(exc, httpx.RequestError):
        return AIProviderError(provider, "provider_unreachable", retryable=True)
    return AIProviderError(provider, "request_failed")


def provider_request_id(response: httpx.Response, data: dict | None = None) -> str:
    for name in ("request-id", "x-request-id", "nv-request-id", "nvcf-reqid"):
        value = response.headers.get(name)
        if value:
            return value[:160]
    if data:
        value = data.get("request_id")
        if isinstance(value, str):
            return value[:160]
    return ""


def token_usage(data: dict, *, anthropic: bool = False) -> tuple[int | None, int | None, int | None]:
    usage = data.get("usage")
    if not isinstance(usage, dict):
        return None, None, None
    input_key = "input_tokens" if anthropic else "prompt_tokens"
    output_key = "output_tokens" if anthropic else "completion_tokens"
    input_tokens = _non_negative_int(usage.get(input_key))
    output_tokens = _non_negative_int(usage.get(output_key))
    total_tokens = _non_negative_int(usage.get("total_tokens"))
    if total_tokens is None and input_tokens is not None and output_tokens is not None:
        total_tokens = input_tokens + output_tokens
    return input_tokens, output_tokens, total_tokens


def _non_negative_int(value) -> int | None:
    return value if isinstance(value, int) and not isinstance(value, bool) and value >= 0 else None


def _retry_after_seconds(value: str | None) -> int | None:
    if not value:
        return None
    try:
        return max(0, int(float(value)))
    except (ValueError, OverflowError):
        try:
            retry_at = parsedate_to_datetime(value)
            if retry_at.tzinfo is None:
                retry_at = retry_at.replace(tzinfo=UTC)
            return max(0, round((retry_at - datetime.now(UTC)).total_seconds()))
        except (TypeError, ValueError, OverflowError):
            return None


def parse_review_json(provider: str, text: str) -> ReviewResponse:
    data = ProviderReviewPayload.model_validate(json.loads(text))
    return ReviewResponse(
        provider=provider,
        decision=data.decision,
        risk_level=data.risk_level,
        reason_codes=data.reason_codes,
        reasons=data.reasons,
        suggested_changes=data.suggested_changes,
    )


def review_prompt(draft_json: str) -> str:
    return (
        "You are a conservative pre-publication safety reviewer for a Mercado Libre listing.\n"
        "Assess only evidence present in the draft. Never invent product facts, certifications, "
        "brand authorization, image contents, or legal conclusions from URLs alone.\n"
        "Check for: prohibited or restricted goods; unsupported medical, safety, performance, or "
        "guarantee claims; trademark, counterfeit, replica, and authorization risk; contradictions "
        "between source and target fields; missing or misleading identity, price, currency, stock, "
        "category, description, or pictures; personal data; and content that needs local-market "
        "or category-specific human verification.\n"
        "Use block for clearly prohibited content, material contradictions, or missing publish-critical "
        "evidence. Use needs_human_review whenever material safety or compliance cannot be proven from "
        "the supplied evidence. Use pass only when no material issue or uncertainty is identified.\n"
        "Return exactly one JSON object with all five keys and no markdown or extra keys: "
        "decision, risk_level, reason_codes, reasons, suggested_changes. "
        "decision must be pass, needs_human_review, or block. risk_level must be low, medium, or high. "
        "The only valid decision/risk combinations are pass/low, needs_human_review/medium, "
        "needs_human_review/high, and block/high. "
        "reason_codes and reasons must be arrays of strings. suggested_changes must be an object.\n\n"
        f"Draft JSON:\n{draft_json}"
    )
