"""Materialize external source pictures into Mercado Libre picture IDs."""

import asyncio
import re
from pathlib import PurePosixPath
from urllib.parse import urlparse

import httpx

from app.services.image_validation import ImageValidationError, normalize_listing_image
from app.services.meli.client import MercadoLibreClient


MAX_PICTURE_BYTES = 10 * 1024 * 1024
ALLOWED_CONTENT_TYPES = {"image/jpeg", "image/jpg", "image/png"}

# Transient failures (timeouts, connection errors, 408/429/5xx) are retried a
# few times with backoff before a job is marked failed. Deterministic 4xx
# rejections (bad image, forbidden source, ...) fail immediately.
MAX_DOWNLOAD_ATTEMPTS = 3
MAX_UPLOAD_ATTEMPTS = 3


class PictureUploadError(ValueError):
    """A deterministic media problem; safe to correct and retry."""


def _retryable_http(status: int) -> bool:
    return status in (408, 429) or 500 <= status <= 599


async def _backoff_delay(attempt: int) -> None:
    await asyncio.sleep(min(0.5 * (2 ** (attempt - 1)), 4.0))


async def _download_with_retry(source: str) -> httpx.Response:
    """Download a source image, retrying transient network/server failures."""
    for attempt in range(1, MAX_DOWNLOAD_ATTEMPTS + 1):
        try:
            async with httpx.AsyncClient(timeout=40, follow_redirects=True) as downloader:
                response = await downloader.get(source)
            response.raise_for_status()
            return response
        except httpx.HTTPStatusError as exc:
            if _retryable_http(exc.response.status_code) and attempt < MAX_DOWNLOAD_ATTEMPTS:
                await _backoff_delay(attempt)
                continue
            raise
        except httpx.HTTPError as exc:
            if attempt < MAX_DOWNLOAD_ATTEMPTS:
                await _backoff_delay(attempt)
                continue
            raise
    raise httpx.TransportError(f"download retries exhausted: {source}")


async def _upload_with_retry(
    client: MercadoLibreClient,
    *,
    content: bytes,
    filename: str,
    content_type: str,
) -> dict | list:
    """Upload a normalized image to Mercado Libre, retrying transient failures.

    A lost response after the server actually stored the picture would create a
    second (orphan) picture id on retry; that is harmless and preferable to a
    job failing because of a transient 5xx/timeout.
    """
    for attempt in range(1, MAX_UPLOAD_ATTEMPTS + 1):
        try:
            return await client.upload_picture(
                content=content, filename=filename, content_type=content_type
            )
        except httpx.HTTPStatusError as exc:
            if _retryable_http(exc.response.status_code) and attempt < MAX_UPLOAD_ATTEMPTS:
                await _backoff_delay(attempt)
                continue
            raise
        except httpx.HTTPError as exc:
            if attempt < MAX_UPLOAD_ATTEMPTS:
                await _backoff_delay(attempt)
                continue
            raise
    raise httpx.TransportError("upload retries exhausted")


async def materialize_global_picture_sources(
    client: MercadoLibreClient,
    payload: dict,
) -> dict:
    """Replace external ``source`` URLs with Mercado Libre-owned picture IDs.

    Amazon CDN URLs may render in a browser but can reject Mercado Libre's
    asynchronous fetcher. Downloading once from our server and using the
    official multipart image endpoint makes the create request deterministic.
    """
    sources: list[str] = []
    for picture in payload.get("pictures", []):
        if isinstance(picture, dict) and isinstance(picture.get("source"), str):
            sources.append(picture["source"])
    for offer in payload.get("sites_to_sell", []):
        if not isinstance(offer, dict):
            continue
        for picture in offer.get("pictures", []):
            if isinstance(picture, dict) and isinstance(picture.get("source"), str):
                sources.append(picture["source"])

    ids_by_source: dict[str, str] = {}
    for source in dict.fromkeys(sources):
        try:
            response = await _download_with_retry(source)
            content_type = response.headers.get("content-type", "").split(";", 1)[0].lower()
            if content_type not in ALLOWED_CONTENT_TYPES:
                raise PictureUploadError(f"图片格式不支持（{content_type or '未知格式'}）")
            if not response.content or len(response.content) > MAX_PICTURE_BYTES:
                raise PictureUploadError("图片为空或超过 10MB")
            try:
                image_data, normalized_type, _original_dimensions, _final_dimensions = normalize_listing_image(
                    response.content, content_type
                )
            except ImageValidationError as exc:
                raise PictureUploadError(f"{exc}：{source}") from exc
            source_name = PurePosixPath(urlparse(source).path).name or "listing-image.jpg"
            source_stem = PurePosixPath(source_name).stem or "listing-image"
            filename = f"{source_stem}.jpg" if normalized_type == "image/jpeg" else source_name
            uploaded = await _upload_with_retry(
                client, content=image_data, filename=filename, content_type=normalized_type
            )
            picture_id = str(uploaded.get("id", "")).strip() if isinstance(uploaded, dict) else ""
            if not picture_id:
                raise PictureUploadError("美客多图片上传未返回图片 ID")
            ids_by_source[source] = picture_id
        except PictureUploadError:
            raise
        except httpx.HTTPStatusError as exc:
            detail = _upload_error_detail(exc.response)
            raise PictureUploadError(
                f"图片无法下载或上传（HTTP {exc.response.status_code}{detail}）：{source}"
            ) from exc
        except httpx.HTTPError as exc:
            raise PictureUploadError(f"图片传输失败：{source}") from exc

    def replace(pictures: list[dict]) -> list[dict]:
        return [
            {"id": ids_by_source[picture["source"]]}
            if isinstance(picture, dict) and picture.get("source") in ids_by_source
            else picture
            for picture in pictures
        ]

    payload["pictures"] = replace(payload.get("pictures", []))
    for offer in payload.get("sites_to_sell", []):
        if isinstance(offer, dict):
            offer["pictures"] = replace(offer.get("pictures", []))
    return payload


def _upload_error_detail(response: httpx.Response) -> str:
    """Keep a concise Mercado Libre / edge error reason without persisting raw bodies."""
    try:
        payload = response.json()
    except ValueError:
        # Non-JSON body (e.g. an OSS/edge error page): keep a short readable hint.
        text = (response.text or "").strip()
        match = re.search(r"<Message>([^<]+)</Message>", text)
        if match:
            return f"：{match.group(1).strip()[:160]}"
        return ""
    if not isinstance(payload, dict):
        return ""
    code = str(payload.get("error") or payload.get("code") or "").strip()
    message = str(payload.get("message") or payload.get("cause") or "").strip()
    summary = ": ".join(part for part in (code, message) if part)[:240]
    return f"：{summary}" if summary else ""
