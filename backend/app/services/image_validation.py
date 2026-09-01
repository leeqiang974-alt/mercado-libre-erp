"""Validate real image bytes before they enter a Mercado Libre listing."""

import struct


MIN_LISTING_IMAGE_EDGE = 500


class ImageValidationError(ValueError):
    pass


def image_dimensions(data: bytes, content_type: str) -> tuple[int, int]:
    """Return real PNG/JPEG pixel dimensions without depending on Pillow."""
    normalized_type = content_type.split(";", 1)[0].strip().lower()
    if normalized_type == "image/png":
        if len(data) < 24 or data[:8] != b"\x89PNG\r\n\x1a\n" or data[12:16] != b"IHDR":
            raise ImageValidationError("PNG 图片数据无效")
        width, height = struct.unpack(">II", data[16:24])
    elif normalized_type in {"image/jpeg", "image/jpg"}:
        if len(data) < 4 or data[:2] != b"\xff\xd8":
            raise ImageValidationError("JPEG 图片数据无效")
        width, height = _jpeg_dimensions(data)
    else:
        raise ImageValidationError(f"图片格式不支持（{normalized_type or '未知格式'}）")
    if width < 1 or height < 1:
        raise ImageValidationError("图片尺寸无效")
    return width, height


def ensure_listing_image_size(data: bytes, content_type: str) -> tuple[int, int]:
    width, height = image_dimensions(data, content_type)
    if width < MIN_LISTING_IMAGE_EDGE or height < MIN_LISTING_IMAGE_EDGE:
        raise ImageValidationError(
            f"图片尺寸 {width}×{height}px，小于美客多至少 "
            f"{MIN_LISTING_IMAGE_EDGE}×{MIN_LISTING_IMAGE_EDGE}px 的要求"
        )
    return width, height


def _jpeg_dimensions(data: bytes) -> tuple[int, int]:
    index = 2
    while index < len(data):
        while index < len(data) and data[index] == 0xFF:
            index += 1
        if index >= len(data):
            break
        marker = data[index]
        index += 1
        if marker in {0xD8, 0xD9, 0x01} or 0xD0 <= marker <= 0xD7:
            continue
        if index + 2 > len(data):
            break
        segment_length = struct.unpack(">H", data[index:index + 2])[0]
        if segment_length < 2 or index + segment_length > len(data):
            break
        if marker in {
            0xC0, 0xC1, 0xC2, 0xC3, 0xC5, 0xC6, 0xC7,
            0xC9, 0xCA, 0xCB, 0xCD, 0xCE, 0xCF,
        }:
            if segment_length < 7:
                break
            height, width = struct.unpack(">HH", data[index + 3:index + 7])
            return width, height
        index += segment_length
    raise ImageValidationError("JPEG 图片数据无效")
