from app.schemas.drafts import ProductDraftCreate
from app.schemas.reviews import ReviewResponse


SENSITIVE_TERMS = ["cure", "treats disease", "guaranteed", "official brand", "replica"]


def review_draft_locally(draft: ProductDraftCreate) -> ReviewResponse:
    reason_codes: list[str] = []
    reasons: list[str] = []
    if not draft.title.strip():
        reason_codes.append("missing_title")
        reasons.append("Title is required before publishing.")
    if not draft.price:
        reason_codes.append("missing_price")
        reasons.append("Price is required before publishing.")
    if not draft.currency:
        reason_codes.append("missing_currency")
        reasons.append("Currency is required before publishing.")
    if draft.stock < 1:
        reason_codes.append("missing_stock")
        reasons.append("Stock must be at least 1 before publishing.")
    if not draft.image_urls:
        reason_codes.append("missing_image")
        reasons.append("At least one image is required before publishing.")
    text = f"{draft.title} {draft.description}".lower()
    if any(term in text for term in SENSITIVE_TERMS):
        reason_codes.append("regulated_claim")
        reasons.append("Draft contains claims or brand language that require human review.")
    if any(code.startswith("missing_") for code in reason_codes):
        decision = "block"
        risk_level = "high"
    elif reason_codes:
        decision = "needs_human_review"
        risk_level = "medium"
    else:
        decision = "pass"
        risk_level = "low"
    return ReviewResponse(
        provider="local_policy",
        decision=decision,
        risk_level=risk_level,
        reason_codes=reason_codes,
        reasons=reasons,
        suggested_changes={},
    )
