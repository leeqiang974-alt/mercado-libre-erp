from app.schemas.drafts import ProductDraftCreate
from app.schemas.publishing import ListingChoice, PublishValidationResult
from app.schemas.reviews import ReviewResponse
from app.services.meli.payload_builder import build_item_payload


def validate_publish_request(
    draft: ProductDraftCreate,
    review: ReviewResponse,
    listing_choice: ListingChoice,
    valid_listing_type_ids: list[str],
    human_approved: bool,
) -> PublishValidationResult:
    errors: list[str] = []
    if not human_approved:
        errors.append("human_approval_required")
    if listing_choice.fulfillment.lower() == "full":
        errors.append("full_fulfillment_excluded")
    if listing_choice.listing_type_id not in valid_listing_type_ids:
        errors.append("listing_type_not_available")
    if review.decision == "block":
        errors.append("ai_review_blocked")
    if review.decision == "needs_human_review" and not human_approved:
        errors.append("ai_review_needs_human_review")
    try:
        build_item_payload(draft, listing_choice)
    except ValueError as exc:
        errors.append(str(exc))
    return PublishValidationResult(allowed=not errors, errors=errors)
