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
        elif effective.status == PublishJobStatus.PUBLISHED:
            partial = _partial_site_error(effective)
            if partial:
                draft.publication_error = partial
            # 【2026-09-18 迭代】发布后美客多后台反馈：item 可能被暂停/审核/关闭
            # （选错类目被弹回、图片/标题违规等）。回查接口会把 item_status
            # 写进 response_summary_json，这里把它反映到草稿列表，让用户看到
            # “已暂停/审核中”而不只是“已发布”。
            item_status = (effective.response_summary_json or {}).get("item_status") or {}
            if isinstance(item_status, dict):
                meli_status = str(item_status.get("status") or "").strip().lower()
                sub = item_status.get("sub_status") or []
                sub_text = ""
                if isinstance(sub, list):
                    sub_text = "、".join(str(s) for s in sub[:3] if s)
                elif isinstance(sub, str) and sub:
                    sub_text = sub
                if meli_status == "paused":
                    draft.publication_status = "paused"
                    draft.publication_error = (
                        "美客多已暂停该商品" + (f"（{sub_text}）" if sub_text else "")
                    )
                elif meli_status == "under_review":
                    draft.publication_status = "under_review"
                    draft.publication_error = (
                        "美客多审核中" + (f"（{sub_text}）" if sub_text else "")
                    )
                elif meli_status == "closed":
                    draft.publication_status = "closed"
                    draft.publication_error = (
                        "美客多已关闭该商品" + (f"（{sub_text}）" if sub_text else "")
                    )
                elif meli_status and meli_status != "active" and not draft.publication_error:
                    draft.publication_status = meli_status
                    draft.publication_error = f"美客多状态：{meli_status}"
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


def _partial_site_error(job: PublishJob) -> str:
    """【2026-09-16 迭代】发布成功但部分站点被拒时提取站点级错误。

    response_details.site_items 中无 item_id 且带 error 的行即失败站点，
    拼接“部分站点失败: MLC(消息)/MLA(消息)”供前端展示。
    """
    summary = job.response_summary_json or {}
    details = summary.get("response_details") or {}
    site_items = details.get("site_items", []) if isinstance(details, dict) else []
    failed: list[str] = []
    for row in site_items:
        if not isinstance(row, dict) or row.get("item_id"):
            continue
        err = row.get("error")
        if not isinstance(err, dict):
            continue
        site_id = str(row.get("site_id") or "").strip()
        causes = err.get("cause") or []
        message = ""
        for cause in causes:
            if isinstance(cause, dict) and str(cause.get("message") or "").strip():
                message = str(cause.get("message") or "").strip()
                break
        failed.append(f"{site_id}({message or 'failed'})" if message else site_id)
    if not failed:
        return ""
    return "部分站点失败: " + "; ".join(failed[:4])
