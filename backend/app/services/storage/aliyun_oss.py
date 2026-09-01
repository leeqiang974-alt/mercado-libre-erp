"""Verified Aliyun OSS mirroring for Mercado Libre source images."""

import asyncio
import hashlib
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import urlsplit

import httpx
import oss2

from app.core.config import Settings
from app.services.image_validation import ImageValidationError, ensure_listing_image_size


MAX_IMAGE_BYTES = 10 * 1024 * 1024
IMAGE_CONTENT_TYPES = {"image/jpeg", "image/jpg", "image/png"}


class OssMirrorError(ValueError):
    pass


def _bucket(settings: Settings) -> oss2.Bucket:
    credential_path = Path(settings.aliyun_oss_credential_file)
    try:
        lines = [line.strip() for line in credential_path.read_text(encoding="utf-8").splitlines() if line.strip()]
    except OSError as exc:
        raise OssMirrorError("OSS 凭证文件不可用") from exc
    if len(lines) < 4:
        raise OssMirrorError("OSS 凭证文件格式无效")
    return oss2.Bucket(
        oss2.Auth(lines[1], lines[3]),
        f"https://{settings.aliyun_oss_endpoint}",
        settings.aliyun_oss_bucket,
    )


def _public_url(settings: Settings, object_key: str) -> str:
    return f"https://{settings.aliyun_oss_bucket}.{settings.aliyun_oss_endpoint}/{object_key}"


async def mirror_image_to_oss(source_url: str, settings: Settings) -> str:
    """Mirror one public JPEG/PNG and verify it before returning its HTTPS URL."""
    already_mirrored = source_url.startswith(
        f"https://{settings.aliyun_oss_bucket}.{settings.aliyun_oss_endpoint}/"
    )
    try:
        async with httpx.AsyncClient(timeout=40, follow_redirects=True) as client:
            response = await client.get(source_url)
        response.raise_for_status()
    except httpx.HTTPError as exc:
        raise OssMirrorError(f"无法下载图片：{source_url}") from exc
    content_type = response.headers.get("content-type", "").split(";", 1)[0].lower()
    if content_type not in IMAGE_CONTENT_TYPES:
        raise OssMirrorError(f"图片格式不支持（{content_type or '未知'}）：{source_url}")
    data = response.content
    if not data or len(data) > MAX_IMAGE_BYTES:
        raise OssMirrorError(f"图片为空或超过 10MB：{source_url}")
    try:
        ensure_listing_image_size(data, content_type)
    except ImageValidationError as exc:
        raise OssMirrorError(f"{exc}：{source_url}") from exc
    if already_mirrored:
        return source_url
    extension = ".png" if content_type == "image/png" else ".jpg"
    digest = hashlib.sha256(data).hexdigest()
    day = datetime.now(UTC).strftime("%Y%m%d")
    object_key = f"{settings.aliyun_oss_prefix.strip('/')}/{day}/{digest[:32]}{extension}"
    bucket = _bucket(settings)
    try:
        if not bucket.object_exists(object_key):
            bucket.put_object(object_key, data, headers={"Content-Type": content_type})
        if bucket.head_object(object_key).status != 200:
            raise OssMirrorError("OSS 图片校验失败")
    except OssMirrorError:
        raise
    except Exception as exc:
        raise OssMirrorError("OSS 图片上传失败") from exc
    return _public_url(settings, object_key)


async def mirror_images_to_oss(urls: list[str], settings: Settings) -> list[str]:
    source_urls = list(dict.fromkeys(
        raw_url.strip()
        for raw_url in urls
        if raw_url.strip()
        and not raw_url.strip().lower().endswith(".gif")
        and "grey-pixel" not in raw_url.lower()
    ))
    # Image mirroring is independent per URL. Run the small listing batch in
    # parallel so the operator request remains inside the API timeout.
    uploaded_urls = await asyncio.gather(
        *(mirror_image_to_oss(source_url, settings) for source_url in source_urls),
        return_exceptions=True,
    )
    by_source: dict[str, str] = {}
    for source_url, uploaded in zip(source_urls, uploaded_urls, strict=True):
        if isinstance(uploaded, OssMirrorError) and (
            "图片格式不支持" in str(uploaded) or "图片尺寸" in str(uploaded)
        ):
            continue
        if isinstance(uploaded, Exception):
            raise uploaded
        by_source[source_url] = uploaded
    mirrored = [by_source[raw_url.strip()] for raw_url in urls if raw_url.strip() in by_source]
    if not mirrored:
        raise OssMirrorError("没有符合美客多至少 500×500px 要求的图片")
    return mirrored
