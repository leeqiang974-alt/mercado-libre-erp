import httpx

from app.schemas.drafts import ProductDraftCreate
from app.schemas.publishing import ListingChoice, PublishExecutionResult, PublishValidationResult
from app.schemas.reviews import ReviewResponse
from app.services.meli.client import MercadoLibreClient
from app.services.meli.payload_builder import (
    SUPPORTED_NON_FULL_LOGISTIC_TYPES,
    build_item_payload,
)
from app.services.meli.shipping import resolve_non_full_shipping
from app.services.meli.sites import expected_currency

SUPPORTED_LISTING_TYPE_IDS = {"gold_special", "gold_pro"}


def validate_store_site_match(store_site_id: str, listing_site_id: str) -> list[str]:
    if store_site_id.strip().upper() == listing_site_id.strip().upper():
        return []
    return ["store_site_mismatch"]


def validate_site_currency(site_id: str, currency: str) -> list[str]:
    required = expected_currency(site_id)
    if required and currency.strip().upper() != required:
        return ["target_currency_mismatch"]
    return []


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
    if listing_choice.fulfillment.strip().lower() == "full":
        errors.append("full_fulfillment_excluded")
    if listing_choice.listing_type_id not in SUPPORTED_LISTING_TYPE_IDS:
        errors.append("listing_type_not_supported")
    if listing_choice.listing_type_id not in valid_listing_type_ids:
        errors.append("listing_type_not_available")
    if review.decision == "block":
        errors.append("ai_review_blocked")
    if review.decision == "needs_human_review" and not human_approved:
        errors.append("ai_review_needs_human_review")
    errors.extend(validate_site_currency(listing_choice.site_id, draft.currency))
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
    seller_id: str = "",
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
    if not seller_id:
        errors.append("seller_id_required")
    if errors:
        return PublishExecutionResult(status="blocked", errors=errors)
    try:
        shipping_preferences = await client.get(f"/users/{seller_id}/shipping_preferences")
    except httpx.HTTPError:
        return PublishExecutionResult(
            status="blocked",
            errors=["shipping_preferences_unavailable"],
        )
    shipping = resolve_non_full_shipping(shipping_preferences)
    if not shipping:
        return PublishExecutionResult(
            status="blocked",
            errors=["non_full_shipping_mode_unavailable"],
        )
    payload = build_item_payload(
        draft,
        listing_choice,
        shipping_mode=shipping.mode,
        shipping_logistic_type=shipping.logistic_type,
    )
    try:
        response = await client.post("/items", payload)
    except httpx.HTTPStatusError as exc:
        if exc.response.status_code >= 500:
            return PublishExecutionResult(
                status="blocked",
                shipping_mode=shipping.mode,
                shipping_logistic_type=shipping.logistic_type,
                errors=["publish_outcome_unknown_manual_reconciliation_required"],
            )
        return PublishExecutionResult(
            status="failed",
            shipping_mode=shipping.mode,
            shipping_logistic_type=shipping.logistic_type,
            errors=[f"meli_publish_failed:{exc.response.status_code}"],
        )
    except httpx.TransportError:
        return PublishExecutionResult(
            status="blocked",
            shipping_mode=shipping.mode,
            shipping_logistic_type=shipping.logistic_type,
            errors=["publish_outcome_unknown_manual_reconciliation_required"],
        )
    except httpx.HTTPError:
        return PublishExecutionResult(
            status="failed",
            shipping_mode=shipping.mode,
            shipping_logistic_type=shipping.logistic_type,
            errors=["meli_publish_unavailable"],
        )
    item_id = str(response.get("id", "")).strip()
    permalink = str(response.get("permalink", "")).strip()
    response_site_id = str(response.get("site_id", "")).strip().upper()
    response_shipping = response.get("shipping") or {}
    actual_mode = str(response_shipping.get("mode", "")).strip().lower()
    actual_logistic_type = str(response_shipping.get("logistic_type", "")).strip().lower()
    verification_errors: list[str] = []
    if not item_id:
        return PublishExecutionResult(
            status="blocked",
            permalink=permalink,
            shipping_mode=actual_mode or shipping.mode,
            shipping_logistic_type=actual_logistic_type or shipping.logistic_type,
            errors=[
                "publish_outcome_unknown_manual_reconciliation_required",
                "meli_publish_response_missing_item_id",
            ],
        )
    if response_site_id != draft.target_site_id.upper():
        verification_errors.append("meli_publish_site_mismatch")
    if actual_mode not in {"me2", "me1", "not_specified"}:
        verification_errors.append("meli_publish_shipping_mode_unverified")
    if actual_logistic_type == "fulfillment":
        verification_errors.append("full_fulfillment_detected")
    elif actual_logistic_type not in SUPPORTED_NON_FULL_LOGISTIC_TYPES:
        verification_errors.append("meli_publish_logistic_type_unverified")
    if verification_errors:
        try:
            close_response = await client.put(f"/items/{item_id}", {"status": "closed"})
            close_status = (
                str(close_response.get("status", "")).strip().lower()
                if isinstance(close_response, dict)
                else ""
            )
            if close_status != "closed":
                verification_errors.extend(
                    [
                        "meli_item_close_unverified",
                        "publish_outcome_unknown_manual_reconciliation_required",
                    ]
                )
        except httpx.HTTPError:
            verification_errors.extend(
                [
                    "meli_item_close_failed",
                    "publish_outcome_unknown_manual_reconciliation_required",
                ]
            )
        return PublishExecutionResult(
            status=(
                "blocked"
                if "publish_outcome_unknown_manual_reconciliation_required"
                in verification_errors
                else "failed"
            ),
            item_id=item_id,
            permalink=permalink,
            shipping_mode=actual_mode or shipping.mode,
            shipping_logistic_type=actual_logistic_type or shipping.logistic_type,
            errors=verification_errors,
        )
    return PublishExecutionResult(
        status="published",
        item_id=item_id,
        permalink=permalink,
        shipping_mode=actual_mode,
        shipping_logistic_type=actual_logistic_type,
        errors=[],
    )
