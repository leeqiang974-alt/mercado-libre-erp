from app.schemas.drafts import ProductDraftCreate
from app.schemas.publishing import ListingChoice, PublishExecutionResult, PublishValidationResult
from app.schemas.reviews import ReviewResponse
from app.services.meli.client import MercadoLibreClient
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


async def execute_publish(
    client: MercadoLibreClient,
    draft: ProductDraftCreate,
    review: ReviewResponse,
    listing_choice: ListingChoice,
    valid_listing_type_ids: list[str],
    human_approved: bool,
    allow_live_publish: bool,
) -> PublishExecutionResult:
    validation = validate_publish_request(
        draft=draft,
        review=review,
        listing_choice=listing_choice,
        valid_listing_type_ids=valid_listing_type_ids,
        human_approved=human_approved,
    )
    errors = list(validation.errors)
    if not allow_live_publish:
        errors.append("live_publish_disabled")
    if not client.access_token:
        errors.append("access_token_required")
    if errors:
        return PublishExecutionResult(status="blocked", errors=errors)
    payload = build_item_payload(draft, listing_choice)
    response = await client.post("/items", payload)
    return PublishExecutionResult(
        status="published",
        item_id=str(response.get("id", "")),
        permalink=response.get("permalink", ""),
        errors=[],
    )
