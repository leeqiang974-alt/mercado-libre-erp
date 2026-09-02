"""Materialize external source pictures into Mercado Libre picture IDs."""

from pathlib import PurePosixPath
from urllib.parse import urlparse

import httpx

from app.services.image_validation import ImageValidationError, normalize_listing_image
from app.services.meli.client import MercadoLibreClient


MAX_PICTURE_BYTES = 10 * 1024 * 1024
ALLOWED_CONTENT_TYPES = {"image/jpeg", "image/jpg", "image/png"}


class PictureUploadError(ValueError):
    """A deterministic media problem; safe to correct and retry."""


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
            async with httpx.AsyncClient(timeout=40, follow_redirects=True) as downloader:
                response = await downloader.get(source)
            response.raise_for_status()
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
            uploaded = await client.upload_picture(
                content=image_data, filename=filename, content_type=normalized_type
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
    """Keep a concise Mercado Libre error reason without persisting raw bodies."""
    try:
        payload = response.json()
    except ValueError:
        return ""
    if not isinstance(payload, dict):
        return ""
    code = str(payload.get("error") or payload.get("code") or "").strip()
    message = str(payload.get("message") or payload.get("cause") or "").strip()
    summary = ": ".join(part for part in (code, message) if part)[:240]
    return f"：{summary}" if summary else ""
