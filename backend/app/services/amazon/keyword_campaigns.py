"""Persistent, rate-controlled Amazon keyword discovery campaigns."""
from collections.abc import Iterable

from sqlalchemy.orm import Session

from app.models.collection_job import CollectionJob
from app.models.keyword_collection_campaign import KeywordCampaignStatus, KeywordCollectionCampaign
from app.services.amazon.discovery import discover_amazon_products
from app.services.collection_jobs import create_collection_jobs


def normalize_keywords(values: Iterable[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for raw in values:
        value = " ".join(raw.split()).strip().lower()
        if len(value) < 2 or value in seen:
            continue
        seen.add(value)
        result.append(value)
    return result


async def run_one_keyword_campaign_step(db: Session) -> dict[str, int]:
    campaign = (db.query(KeywordCollectionCampaign)
                .filter(KeywordCollectionCampaign.status.in_([KeywordCampaignStatus.PENDING.value, KeywordCampaignStatus.RUNNING.value]))
                .order_by(KeywordCollectionCampaign.id).with_for_update(skip_locked=True).first())
    if campaign is None:
        return {"campaigns": 0, "queued": 0}
    keywords = campaign.keywords_json or []
    if campaign.current_keyword_index >= len(keywords):
        campaign.status = KeywordCampaignStatus.COMPLETED.value
        campaign.message = "关键词发现已完成；详情采集队列仍会继续处理。"
        db.commit()
        return {"campaigns": 1, "queued": 0}

    keyword = keywords[campaign.current_keyword_index]
    campaign.status = KeywordCampaignStatus.RUNNING.value
    campaign.message = f"正在发现：{keyword}（第 {campaign.current_page}/{campaign.pages_per_keyword} 页）"
    db.commit()
    try:
        result = await discover_amazon_products(campaign.domain, keyword, 50, campaign.current_page)
    except Exception as exc:
        campaign.message = f"{keyword} 暂未完成：{str(exc)[:180]}"
        db.commit()
        return {"campaigns": 1, "queued": 0}
    if result.challenge_detected:
        campaign.status = KeywordCampaignStatus.PAUSED.value
        campaign.message = f"Amazon 要求验证，已暂停在关键词：{keyword}"
        db.commit()
        return {"campaigns": 1, "queued": 0}
    if not result.product_urls:
        # Zero search cards is not a successful empty keyword: Amazon often
        # returns a verification/interstitial page that has no ASIN cards.
        # Stop visibly instead of silently burning through the keyword list.
        campaign.status = KeywordCampaignStatus.PAUSED.value
        campaign.message = f"{keyword} 未返回可验证商品卡片，已暂停等待采集页面诊断。"
        db.commit()
        return {"campaigns": 1, "queued": 0}

    existing = {row[0] for row in db.query(CollectionJob.source_identity).filter(CollectionJob.target_site_id == campaign.target_site_id, CollectionJob.source_identity.in_(result.product_urls)).all()}
    new_urls = [url for url in result.product_urls if url not in existing]
    if new_urls:
        create_collection_jobs(db, [(url, campaign.target_site_id) for url in new_urls])
    campaign.discovered_count += len(result.product_urls)
    campaign.queued_count += len(new_urls)
    campaign.duplicate_count += len(result.product_urls) - len(new_urls)
    if campaign.current_page >= campaign.pages_per_keyword:
        campaign.current_keyword_index += 1
        campaign.current_page = 1
    else:
        campaign.current_page += 1
    campaign.message = f"已发现 {campaign.discovered_count} 个链接，已入队 {campaign.queued_count} 个。"
    db.commit()
    return {"campaigns": 1, "queued": len(new_urls)}
