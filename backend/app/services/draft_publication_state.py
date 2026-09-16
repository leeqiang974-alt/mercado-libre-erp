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
        if effective.status in (PublishJobStatus.FAILED, PublishJobStatus.BLOCKED):
            draft.publication_error = _publication_error(effective)
    return rows


def _publication_error(job: PublishJob) -> str:
    """从最近失败/阻塞任务的响应里提取可读错误（前 2 条，截断 300 字符）。"""
    summary = job.response_summary_json or {}
    errors = list(summary.get("errors") or [])
    # 【2026-09-16 迭代】部分站点失败（item.not_allowed 等分类不允许错误）在
    # response_details.site_items[].error.cause 里，顶层 errors 为空时不显示。
    # 把它并入可读错误，让用户看到“分类不被允许：XX 站点”。
    details = summary.get("response_details") or {}
    site_items = details.get("site_items", []) if isinstance(details, dict) else []
    site_not_allowed = []
    for row in site_items:
        if not isinstance(row, dict):
            continue
        err = row.get("error")
        if not isinstance(err, dict):
            continue
        site_id = str(row.get("site_id") or "").strip()
        for cause in err.get("cause") or []:
            if not isinstance(cause, dict):
                continue
            code = str(cause.get("code") or "")
            message = str(cause.get("message") or "").strip()
            if code in ("item.not_allowed", "category.not_allowed", "invalid.category_id") or "categor" in code.lower():
                site_not_allowed.append(f"{site_id}: {message}")
    if site_not_allowed:
        errors.append("分类不被允许: " + "; ".join(site_not_allowed[:4]))
    if not errors:
        return job.status.value
    joined = "; ".join(str(e) for e in errors[:2])
    return joined[:300]


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
