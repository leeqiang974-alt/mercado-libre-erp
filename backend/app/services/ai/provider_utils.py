from datetime import UTC, datetime
from email.utils import parsedate_to_datetime
import json

import httpx

from app.schemas.reviews import ReviewResponse

REVIEW_PROMPT_VERSION = "meli-safety-v1"


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
    data = json.loads(text)
    return ReviewResponse(
        provider=provider,
        decision=data.get("decision", "needs_human_review"),
        risk_level=data.get("risk_level", "medium"),
        reason_codes=data.get("reason_codes", []),
        reasons=data.get("reasons", []),
        suggested_changes=data.get("suggested_changes", {}),
    )


def review_prompt(draft_json: str) -> str:
    return (
        "Review this marketplace product draft for Mercado Libre listing safety. "
        "Return only JSON with keys: decision, risk_level, reason_codes, reasons, suggested_changes. "
        "Allowed decision values: pass, needs_human_review, block.\n\n"
        f"Draft JSON:\n{draft_json}"
    )
