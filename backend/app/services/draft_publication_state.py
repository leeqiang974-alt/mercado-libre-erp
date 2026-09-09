from collections.abc import Iterable

from sqlalchemy.orm import Session

from app.models.publish_job import PublishJob, PublishJobStatus
from app.schemas.drafts import ProductDraftRead


_DUPLICATE_ERROR_MARKERS = (
    "listing.conflict",
    "This listing already exists",
    "only support 1 item",
)


def apply_draft_publication_state(
    db: Session,
    drafts: Iterable[ProductDraftRead],
) -> list[ProductDraftRead]:
    rows = list(drafts)
    draft_ids = {draft.id for draft in rows}
    if not draft_ids:
        return rows
    jobs = (
        db.query(PublishJob)
        .filter(PublishJob.product_draft_id.in_(draft_ids))
        .order_by(PublishJob.id.desc())
        .all()
    )
    grouped: dict[int, list[PublishJob]] = {}
    for job in jobs:
        grouped.setdefault(job.product_draft_id, []).append(job)
    for draft in rows:
        effective = _effective_job(grouped.get(draft.id, []))
        if effective is None:
            continue
        draft.publication_status = effective.status.value
        draft.published_sites = _published_sites(effective)
    return rows


def _effective_job(jobs: list[PublishJob]) -> PublishJob | None:
    # Once Mercado Libre returned a real item ID, a later retry/failure cannot
    # make that listing cease to exist. Prefer the newest confirmed success.
    published = next(
        (job for job in jobs if job.status == PublishJobStatus.PUBLISHED),
        None,
    )
    if published is not None:
        return published
    return next((job for job in jobs if not _is_duplicate_failure(job)), None)


def _is_duplicate_failure(job: PublishJob) -> bool:
    if job.status != PublishJobStatus.FAILED:
        return False
    errors = (job.response_summary_json or {}).get("errors", [])
    joined = " ".join(str(error) for error in errors)
    return any(marker in joined for marker in _DUPLICATE_ERROR_MARKERS)


def _published_sites(job: PublishJob) -> list[str]:
    if job.status != PublishJobStatus.PUBLISHED:
        return []
    details = (job.response_summary_json or {}).get("response_details", {})
    site_items = details.get("site_items", []) if isinstance(details, dict) else []
    sites = [
        str(row.get("site_id"))
        for row in site_items
        if isinstance(row, dict) and row.get("item_id") and row.get("site_id")
    ]
    return list(dict.fromkeys(sites)) or (["CBT"] if job.meli_item_id else [])
