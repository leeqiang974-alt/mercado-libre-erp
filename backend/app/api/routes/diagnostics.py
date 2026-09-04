"""Global system diagnostics: aggregated publish errors, cross-table search,
and stale/queued job visibility. This is the single place to answer
"what keeps failing / what is stuck right now" without tailing logs.
"""
from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Depends, Query
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.audit_event import AuditEvent
from app.models.product_draft import ProductDraft
from app.models.publish_job import PublishJob, PublishJobStatus
from app.models.store import Store

router = APIRouter(prefix="/api/system/diagnostics", tags=["diagnostics"])

TERMINAL_FAILURE = (PublishJobStatus.FAILED, PublishJobStatus.BLOCKED)
NON_SUCCESS = (
    PublishJobStatus.FAILED,
    PublishJobStatus.BLOCKED,
    PublishJobStatus.PENDING,
    PublishJobStatus.VALIDATING,
)


def _iso(value: datetime | None) -> str | None:
    return value.isoformat() if value else None


def _error_kind(message: str) -> str:
    """Normalize a raw error message into a stable bucket for aggregation."""
    if "图片上传失败" in message:
        return "图片上传失败"
    if "listing.conflict" in message or "already exists" in message:
        return "重复发布 (listing.conflict)"
    if "invalid.listing_type_id" in message:
        return "刊登类型无效 (invalid.listing_type_id)"
    if "global_publish_outcome_unknown" in message:
        return "发布结果未知 · 需人工核对"
    if "only support 1 item" in message:
        return "仅支持单商品 (user_products)"
    if "operator_confirmed_item_not_created" in message:
        return "操作确认但未创建商品"
    if "store_access_token_required" in message:
        return "店铺授权缺失 (token)"
    if "traditional_cbt_seller_required" in message:
        return "非传统 CBT 卖家"
    if "publish_acknowledgement_required" in message:
        return "未确认发布"
    if "live_publish_disabled" in message:
        return "真实刊登未启用"
    return (message or "")[:80] or "(empty)"


def _job_errors(job: PublishJob) -> list[str]:
    return list((job.response_summary_json or {}).get("errors", []) or [])


@router.get("/summary")
def diagnostics_summary(
    days: int = Query(default=7, ge=1, le=90),
    db: Session = Depends(get_db),
) -> dict:
    cutoff = datetime.now(UTC) - timedelta(days=days)
    jobs = db.query(PublishJob).filter(PublishJob.created_at >= cutoff).all()

    totals = {status.value: 0 for status in PublishJobStatus}
    for job in jobs:
        totals[job.status.value] += 1
    totals["total"] = len(jobs)

    kind_counts: dict[str, dict] = {}
    for job in jobs:
        if job.status not in TERMINAL_FAILURE:
            continue
        for err in _job_errors(job):
            kind = _error_kind(err)
            bucket = kind_counts.setdefault(
                kind, {"kind": kind, "count": 0, "sample_draft_ids": []}
            )
            bucket["count"] += 1
            if job.product_draft_id not in bucket["sample_draft_ids"]:
                bucket["sample_draft_ids"].append(job.product_draft_id)
    top_errors = sorted(kind_counts.values(), key=lambda b: -b["count"])[:12]

    stale_jobs = []
    for job in jobs:
        if job.status not in (PublishJobStatus.PENDING, PublishJobStatus.VALIDATING):
            continue
        marker = job.started_at or job.created_at
        age = int((datetime.now(UTC) - marker).total_seconds()) if marker else None
        stale_jobs.append(
            {
                "job_id": job.id,
                "draft_id": job.product_draft_id,
                "status": job.status.value,
                "created_at": _iso(job.created_at),
                "age_seconds": age,
            }
        )

    failures = sorted(
        (j for j in jobs if j.status in TERMINAL_FAILURE),
        key=lambda j: j.id,
        reverse=True,
    )
    recent_failures = []
    for job in failures[:10]:
        draft_title = (
            db.query(ProductDraft.title)
            .filter(ProductDraft.id == job.product_draft_id)
            .scalar()
        )
        recent_failures.append(
            {
                "job_id": job.id,
                "draft_id": job.product_draft_id,
                "draft_title": draft_title or "",
                "status": job.status.value,
                "errors": _job_errors(job),
                "created_at": _iso(job.created_at),
                "item_id": job.meli_item_id or "",
            }
        )

    return {
        "days": days,
        "totals": totals,
        "top_errors": top_errors,
        "stale_jobs": stale_jobs,
        "recent_failures": recent_failures,
    }


@router.get("/errors")
def list_diagnostic_errors(
    status: str | None = Query(default=None, pattern="^(failed|blocked|non-published)$"),
    days: int = Query(default=7, ge=1, le=90),
    q: str = Query(default="", max_length=200),
    draft_id: int | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
) -> dict:
    base = db.query(PublishJob).filter(
        PublishJob.created_at >= datetime.now(UTC) - timedelta(days=days)
    )
    if status == "failed":
        base = base.filter(PublishJob.status == PublishJobStatus.FAILED)
    elif status == "blocked":
        base = base.filter(PublishJob.status == PublishJobStatus.BLOCKED)
    elif status == "non-published":
        base = base.filter(PublishJob.status.in_(NON_SUCCESS))
    else:
        base = base.filter(PublishJob.status.in_(TERMINAL_FAILURE))
    if draft_id:
        base = base.filter(PublishJob.product_draft_id == draft_id)

    rows = base.order_by(PublishJob.id.desc()).limit(500).all()
    if q:
        needle = q.lower()
        rows = [
            r
            for r in rows
            if needle in " ".join(_job_errors(r)).lower()
            or needle == str(r.id)
            or needle == str(r.product_draft_id)
        ]

    titles: dict[int, str] = {}
    draft_ids = {r.product_draft_id for r in rows}
    if draft_ids:
        for d_id, title in (
            db.query(ProductDraft.id, ProductDraft.title)
            .filter(ProductDraft.id.in_(draft_ids))
            .all()
        ):
            titles[d_id] = title

    items = []
    for job in rows[offset : offset + limit]:
        items.append(
            {
                "job_id": job.id,
                "draft_id": job.product_draft_id,
                "draft_title": titles.get(job.product_draft_id, ""),
                "status": job.status.value,
                "errors": _job_errors(job),
                "item_id": job.meli_item_id or "",
                "permalink": job.permalink or "",
                "created_at": _iso(job.created_at),
                "completed_at": _iso(job.completed_at),
                "started_at": _iso(job.started_at),
            }
        )

    return {"total": len(rows), "limit": limit, "offset": offset, "items": items}


@router.get("/search")
def global_search(
    q: str = Query(min_length=1, max_length=200),
    limit: int = Query(default=20, ge=1, le=50),
    db: Session = Depends(get_db),
) -> dict:
    needle = q.strip()
    results: dict = {"drafts": [], "publish_jobs": [], "audit_events": [], "stores": []}

    if needle.isdigit():
        numeric = int(needle)
        draft = db.get(ProductDraft, numeric)
        if draft is not None:
            results["drafts"].append(
                {
                    "id": draft.id,
                    "title": draft.title,
                    "status": draft.status.value,
                    "target_site_id": draft.target_site_id,
                    "target_category_id": draft.target_category_id,
                }
            )
        job = db.query(PublishJob).filter(PublishJob.id == numeric).first()
        if job is not None:
            results["publish_jobs"].append(
                {
                    "job_id": job.id,
                    "draft_id": job.product_draft_id,
                    "status": job.status.value,
                    "errors": _job_errors(job),
                    "item_id": job.meli_item_id or "",
                    "created_at": _iso(job.created_at),
                }
            )

    pattern = f"%{needle}%"
    for draft in (
        db.query(ProductDraft)
        .filter(ProductDraft.title.ilike(pattern))
        .order_by(ProductDraft.id.desc())
        .limit(limit)
        .all()
    ):
        results["drafts"].append(
            {
                "id": draft.id,
                "title": draft.title,
                "status": draft.status.value,
                "target_site_id": draft.target_site_id,
                "target_category_id": draft.target_category_id,
            }
        )

    for job in (
        db.query(PublishJob)
        .order_by(PublishJob.id.desc())
        .limit(500)
        .all()
    ):
        haystack = " ".join(
            [
                str(job.id),
                str(job.product_draft_id),
                job.meli_item_id or "",
                job.permalink or "",
                " ".join(_job_errors(job)),
            ]
        ).lower()
        if needle.lower() not in haystack:
            continue
        results["publish_jobs"].append(
            {
                "job_id": job.id,
                "draft_id": job.product_draft_id,
                "status": job.status.value,
                "errors": _job_errors(job),
                "item_id": job.meli_item_id or "",
                "created_at": _iso(job.created_at),
            }
        )
        if len(results["publish_jobs"]) >= limit:
            break

    for event in (
        db.query(AuditEvent)
        .filter(
            or_(
                AuditEvent.action.ilike(pattern),
                AuditEvent.entity_id.ilike(pattern),
                AuditEvent.actor_id.ilike(pattern),
            )
        )
        .order_by(AuditEvent.id.desc())
        .limit(limit)
        .all()
    ):
        results["audit_events"].append(
            {
                "id": event.id,
                "action": event.action,
                "entity_type": event.entity_type,
                "entity_id": event.entity_id,
                "actor_id": event.actor_id,
                "created_at": _iso(event.created_at),
            }
        )

    for store in (
        db.query(Store)
        .filter(
            or_(
                Store.display_name.ilike(pattern),
                Store.seller_id.ilike(pattern),
                Store.site_id.ilike(pattern),
            )
        )
        .limit(limit)
        .all()
    ):
        results["stores"].append(
            {
                "id": store.id,
                "display_name": store.display_name,
                "seller_id": store.seller_id,
                "site_id": store.site_id,
                "oauth_status": store.oauth_status,
            }
        )

    return {"q": q, "results": results}
