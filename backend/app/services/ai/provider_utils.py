import json

from app.schemas.reviews import ReviewResponse


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
