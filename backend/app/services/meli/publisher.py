import asyncio

import httpx

from app.schemas.draft_listing_config import SUPPORTED_LISTING_TYPE_IDS
from app.schemas.drafts import ProductDraftCreate
from app.schemas.publishing import ListingChoice, PublishExecutionResult, PublishValidationResult
from app.schemas.reviews import ReviewResponse
from app.services.meli.client import MercadoLibreClient, MercadoLibreResponseError
from app.services.meli.payload_builder import (
    SUPPORTED_NON_FULL_LOGISTIC_TYPES,
    SUPPORTED_SHIPPING_MODES,
    build_description_payload,
    build_item_payload,
)
from app.services.meli.shipping import (
    find_non_full_shipping_selection,
    resolve_non_full_shipping,
)
from app.services.meli.sites import expected_currency

def validate_store_site_match(store_site_id: str, listing_site_id: str) -> list[str]:
    if store_site_id.strip().upper() == listing_site_id.strip().upper():
        return []
    return ["store_site_mismatch"]


def validate_site_currency(site_id: str, currency: str) -> list[str]:
    required = expected_currency(site_id)
    if required and currency.strip().upper() != required:
        return ["target_currency_mismatch"]
    return []


def validate_delivery_binding(
    execution_store_id: int | None, listing_choice: ListingChoice
) -> list[str]:
    errors: list[str] = []
    if listing_choice.store_id is None:
        errors.append("authorized_store_selection_required")
    elif execution_store_id is not None and listing_choice.store_id != execution_store_id:
        errors.append("configured_store_mismatch")
    if not listing_choice.shipping_mode or not listing_choice.shipping_logistic_type:
        errors.append("non_full_shipping_selection_required")
    return errors


def validate_store_delivery(
    store_id: int,
    store_site_id: str,
    oauth_status: str,
    listing_choice: ListingChoice,
) -> list[str]:
    return [
        *validate_store_site_match(store_site_id, listing_choice.site_id),
        *validate_delivery_binding(store_id, listing_choice),
        *([] if oauth_status == "connected" else ["store_not_connected"]),
    ]


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
        build_item_payload(
            draft,
            listing_choice,
            shipping_mode=listing_choice.shipping_mode or None,
            shipping_logistic_type=listing_choice.shipping_logistic_type or None,
        )
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
    publish_reference: str = "",
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
    if listing_choice.shipping_mode and listing_choice.shipping_logistic_type:
        shipping = find_non_full_shipping_selection(
            shipping_preferences,
            listing_choice.shipping_mode,
            listing_choice.shipping_logistic_type,
        )
        if not shipping:
            return PublishExecutionResult(
                status="blocked",
                errors=["selected_non_full_shipping_option_unavailable"],
            )
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
        seller_custom_field=publish_reference,
    )
    try:
        response = await client.post("/items", payload)
    except MercadoLibreResponseError:
        return PublishExecutionResult(
            status="blocked",
            shipping_mode=shipping.mode,
            shipping_logistic_type=shipping.logistic_type,
            errors=["publish_outcome_unknown_manual_reconciliation_required"],
        )
    except httpx.HTTPStatusError as exc:
        if exc.response.status_code >= 500 or exc.response.status_code == 408:
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
    authoritative_response = response
    permalink = str(response.get("permalink", "")).strip()
    verification_errors: list[str] = []
    if not item_id:
        return PublishExecutionResult(
            status="blocked",
            permalink=permalink,
            shipping_mode=shipping.mode,
            shipping_logistic_type=shipping.logistic_type,
            errors=[
                "publish_outcome_unknown_manual_reconciliation_required",
                "meli_publish_response_missing_item_id",
            ],
        )
    if publish_reference:
        if not all(
            key in response
            for key in (
                "seller_custom_field",
                "seller_id",
                "category_id",
                "listing_type_id",
                "shipping",
                "status",
            )
        ):
            try:
                item_readback = await client.get(f"/items/{item_id}")
            except httpx.HTTPError:
                item_readback = None
            if isinstance(item_readback, dict):
                authoritative_response = item_readback
        verification_errors.extend(
            _verify_publish_identity(
                authoritative_response,
                seller_id=seller_id,
                publish_reference=publish_reference,
                site_id=draft.target_site_id,
                category_id=draft.target_category_id,
                listing_type_id=listing_choice.listing_type_id,
            )
        )
    elif str(response.get("site_id", "")).strip().upper() != draft.target_site_id.upper():
        verification_errors.append("meli_publish_site_mismatch")
    authoritative_shipping = authoritative_response.get("shipping") or {}
    actual_mode = str(authoritative_shipping.get("mode", "")).strip().lower()
    actual_logistic_type = str(
        authoritative_shipping.get("logistic_type", "")
    ).strip().lower()
    permalink = str(authoritative_response.get("permalink", "")).strip() or permalink
    if actual_mode not in SUPPORTED_SHIPPING_MODES:
        verification_errors.append("meli_publish_shipping_mode_unverified")
    elif actual_mode != shipping.mode:
        verification_errors.append("meli_publish_shipping_mode_mismatch")
    if actual_logistic_type == "fulfillment":
        verification_errors.append("full_fulfillment_detected")
    elif actual_logistic_type not in SUPPORTED_NON_FULL_LOGISTIC_TYPES:
        verification_errors.append("meli_publish_logistic_type_unverified")
    elif actual_logistic_type != shipping.logistic_type:
        verification_errors.append("meli_publish_logistic_type_mismatch")
    identity_confirmed = not any(
        error in {"meli_publish_reference_mismatch", "meli_publish_seller_mismatch"}
        for error in verification_errors
    )
    item_status = str(authoritative_response.get("status", "")).strip().lower()
    if publish_reference and item_status != "active":
        verification_errors.append("meli_publish_item_status_unverified")
    if verification_errors:
        if identity_confirmed and (item_status == "active" or not publish_reference):
            verification_errors.extend(await _close_item(client, item_id))
        else:
            verification_errors.append(
                "publish_outcome_unknown_manual_reconciliation_required"
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
    description_errors = await _create_or_reconcile_description(
        client, item_id, build_description_payload(draft)["plain_text"]
    )
    if description_errors:
        description_errors.extend(await _close_item(client, item_id))
        return PublishExecutionResult(
            status=(
                "blocked"
                if "publish_outcome_unknown_manual_reconciliation_required"
                in description_errors
                else "failed"
            ),
            item_id=item_id,
            permalink=permalink,
            shipping_mode=actual_mode,
            shipping_logistic_type=actual_logistic_type,
            errors=description_errors,
        )
    return PublishExecutionResult(
        status="published",
        item_id=item_id,
        permalink=permalink,
        shipping_mode=actual_mode,
        shipping_logistic_type=actual_logistic_type,
        errors=[],
    )


async def _create_or_reconcile_description(
    client: MercadoLibreClient, item_id: str, plain_text: str
) -> list[str]:
    try:
        await client.post(f"/items/{item_id}/description", {"plain_text": plain_text})
        return []
    except httpx.HTTPStatusError as exc:
        if exc.response.status_code < 500 and exc.response.status_code != 408:
            try:
                description = await client.get(f"/items/{item_id}/description")
            except httpx.HTTPError:
                description = None
            if isinstance(description, dict) and _normalized_description(
                description.get("plain_text", "")
            ) == _normalized_description(plain_text):
                return []
            return [f"meli_description_failed:{exc.response.status_code}"]
    except httpx.HTTPError:
        pass
    for delay in (0, 0.2, 0.5):
        if delay:
            await asyncio.sleep(delay)
        try:
            description = await client.get(f"/items/{item_id}/description")
        except httpx.HTTPError:
            continue
        if not isinstance(description, dict):
            continue
        if _normalized_description(
            description.get("plain_text", "")
        ) == _normalized_description(plain_text):
            return []
    return ["meli_description_outcome_unverified"]


async def _close_item(client: MercadoLibreClient, item_id: str) -> list[str]:
    try:
        close_response = await client.put(f"/items/{item_id}", {"status": "closed"})
    except httpx.HTTPError:
        return [
            "meli_item_close_failed",
            "publish_outcome_unknown_manual_reconciliation_required",
        ]
    close_status = (
        str(close_response.get("status", "")).strip().lower()
        if isinstance(close_response, dict)
        else ""
    )
    if close_status == "closed":
        return []
    return [
        "meli_item_close_unverified",
        "publish_outcome_unknown_manual_reconciliation_required",
    ]


def _normalized_description(value: object) -> str:
    return str(value).replace("\r\n", "\n").replace("\r", "\n").strip()


def _verify_publish_identity(
    item: dict,
    *,
    seller_id: str,
    publish_reference: str,
    site_id: str,
    category_id: str,
    listing_type_id: str,
) -> list[str]:
    errors: list[str] = []
    if str(item.get("seller_custom_field", "")).strip() != publish_reference:
        errors.append("meli_publish_reference_mismatch")
    if str(item.get("seller_id", "")).strip() != seller_id:
        errors.append("meli_publish_seller_mismatch")
    if str(item.get("site_id", "")).strip().upper() != site_id.strip().upper():
        errors.append("meli_publish_site_mismatch")
    if str(item.get("category_id", "")).strip().upper() != category_id.strip().upper():
        errors.append("meli_publish_category_mismatch")
    if str(item.get("listing_type_id", "")).strip() != listing_type_id:
        errors.append("meli_publish_listing_type_mismatch")
    return errors


async def reconcile_existing_publish(
    client: MercadoLibreClient,
    item: dict,
    *,
    seller_id: str,
    publish_reference: str,
    site_id: str,
    category_id: str,
    listing_type_id: str,
    expected_shipping_mode: str,
    expected_shipping_logistic_type: str,
    expected_item_id: str,
    description: str,
) -> PublishExecutionResult:
    observed_item_id = str(item.get("id", "")).strip()
    expected_item_id = expected_item_id.strip()
    item_id = observed_item_id if observed_item_id == expected_item_id else ""
    permalink = str(item.get("permalink", "")).strip()
    shipping = item.get("shipping") or {}
    shipping_mode = str(shipping.get("mode", "")).strip().lower()
    logistic_type = str(shipping.get("logistic_type", "")).strip().lower()
    errors = _verify_publish_identity(
        item,
        seller_id=seller_id,
        publish_reference=publish_reference,
        site_id=site_id,
        category_id=category_id,
        listing_type_id=listing_type_id,
    )
    if observed_item_id != expected_item_id:
        errors.append("meli_publish_item_id_mismatch")
    if shipping_mode not in SUPPORTED_SHIPPING_MODES:
        errors.append("meli_publish_shipping_mode_unverified")
    elif shipping_mode != expected_shipping_mode.strip().lower():
        errors.append("meli_publish_shipping_mode_mismatch")
    if logistic_type == "fulfillment":
        errors.append("full_fulfillment_detected")
    elif logistic_type not in SUPPORTED_NON_FULL_LOGISTIC_TYPES:
        errors.append("meli_publish_logistic_type_unverified")
    elif logistic_type != expected_shipping_logistic_type.strip().lower():
        errors.append("meli_publish_logistic_type_mismatch")
    identity_confirmed = not any(
        error
        in {
            "meli_publish_reference_mismatch",
            "meli_publish_seller_mismatch",
            "meli_publish_item_id_mismatch",
        }
        for error in errors
    )
    item_status = str(item.get("status", "")).strip().lower()
    if item_status != "active":
        errors.append("meli_publish_item_status_unverified")
    if errors:
        if item_id and identity_confirmed and item_status == "active":
            errors.extend(await _close_item(client, item_id))
        elif not identity_confirmed or item_status != "active":
            errors.append("publish_outcome_unknown_manual_reconciliation_required")
        return PublishExecutionResult(
            status=(
                "blocked"
                if "publish_outcome_unknown_manual_reconciliation_required" in errors
                else "failed"
            ),
            item_id=item_id,
            permalink=permalink,
            shipping_mode=shipping_mode,
            shipping_logistic_type=logistic_type,
            errors=errors,
        )
    description_errors = await _reconcile_existing_description(
        client, item_id, description
    )
    if description_errors:
        if description_errors == ["meli_description_reconciliation_unavailable"]:
            description_errors.append(
                "publish_outcome_unknown_manual_reconciliation_required"
            )
            return PublishExecutionResult(
                status="blocked",
                item_id=item_id,
                permalink=permalink,
                shipping_mode=shipping_mode,
                shipping_logistic_type=logistic_type,
                errors=description_errors,
            )
        description_errors.extend(await _close_item(client, item_id))
        return PublishExecutionResult(
            status=(
                "blocked"
                if "publish_outcome_unknown_manual_reconciliation_required"
                in description_errors
                else "failed"
            ),
            item_id=item_id,
            permalink=permalink,
            shipping_mode=shipping_mode,
            shipping_logistic_type=logistic_type,
            errors=description_errors,
        )
    return PublishExecutionResult(
        status="published",
        item_id=item_id,
        permalink=permalink,
        shipping_mode=shipping_mode,
        shipping_logistic_type=logistic_type,
        errors=[],
    )


async def _reconcile_existing_description(
    client: MercadoLibreClient, item_id: str, plain_text: str
) -> list[str]:
    try:
        description = await client.get(f"/items/{item_id}/description")
    except httpx.HTTPStatusError as exc:
        if exc.response.status_code != 404:
            return ["meli_description_reconciliation_unavailable"]
    except httpx.HTTPError:
        return ["meli_description_reconciliation_unavailable"]
    else:
        if not isinstance(description, dict):
            return ["meli_description_reconciliation_unavailable"]
        if _normalized_description(
            description.get("plain_text", "")
        ) == _normalized_description(plain_text):
            return []
        return ["meli_description_mismatch"]
    return await _create_or_reconcile_description(client, item_id, plain_text)
