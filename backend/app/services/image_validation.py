"""Validate and normalize product image bytes for Mercado Libre."""

from io import BytesIO
from pathlib import Path
import struct
import sys

# The production image carries Pillow. During a low-memory rolling upgrade the
# optional bind-mounted vendor folder lets the running image load the exact same
# library without rebuilding all Playwright dependencies.
_VENDOR_PATH = Path(__file__).parents[1] / "_vendor"
if _VENDOR_PATH.is_dir():
    sys.path.insert(0, str(_VENDOR_PATH))

from PIL import Image, ImageOps, UnidentifiedImageError  # noqa: E402


MIN_LISTING_IMAGE_EDGE = 500
MIN_RESIZABLE_SOURCE_IMAGE_EDGE = 100
MAX_NORMALIZED_IMAGE_BYTES = 10 * 1024 * 1024


class ImageValidationError(ValueError):
    pass


def image_dimensions(data: bytes, content_type: str) -> tuple[int, int]:
    """Return real PNG/JPEG pixel dimensions without depending on URL hints."""
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


def normalize_listing_image(data: bytes, content_type: str) -> tuple[bytes, str, tuple[int, int], tuple[int, int]]:
    """Keep valid images unchanged, or locally upscale eligible small images.

    This is deterministic image processing only: no AI service is called.  Tiny
    source assets are usually icons/thumbnails, so any edge below 100 px stays
    rejected instead of producing a blurred 500 px listing image.
    """
    original_dimensions = image_dimensions(data, content_type)
    width, height = original_dimensions
    if width < MIN_RESIZABLE_SOURCE_IMAGE_EDGE or height < MIN_RESIZABLE_SOURCE_IMAGE_EDGE:
        raise ImageValidationError(
            f"图片尺寸 {width}×{height}px，任一边小于 "
            f"{MIN_RESIZABLE_SOURCE_IMAGE_EDGE}px，不能用于自动放大"
        )
    if width >= MIN_LISTING_IMAGE_EDGE and height >= MIN_LISTING_IMAGE_EDGE:
        return data, content_type, original_dimensions, original_dimensions

    try:
        with Image.open(BytesIO(data)) as source:
            source.load()
            image = ImageOps.exif_transpose(source)
            scale = max(MIN_LISTING_IMAGE_EDGE / image.width, MIN_LISTING_IMAGE_EDGE / image.height)
            target_size = (
                max(MIN_LISTING_IMAGE_EDGE, round(image.width * scale)),
                max(MIN_LISTING_IMAGE_EDGE, round(image.height * scale)),
            )
            # A normal Amazon listing image will remain well below this bound.
            # Do not allow a pathological panorama to exhaust the API worker.
            if target_size[0] * target_size[1] > 30_000_000:
                raise ImageValidationError("图片比例异常，自动放大后像素过大")
            image = image.resize(target_size, Image.Resampling.LANCZOS)
            if image.mode in {"RGBA", "LA"} or (image.mode == "P" and "transparency" in image.info):
                background = Image.new("RGB", image.size, "white")
                background.paste(image.convert("RGBA"), mask=image.convert("RGBA").getchannel("A"))
                image = background
            elif image.mode != "RGB":
                image = image.convert("RGB")
            output = BytesIO()
            image.save(output, format="JPEG", quality=90, optimize=True)
    except ImageValidationError:
        raise
    except (OSError, UnidentifiedImageError) as exc:
        raise ImageValidationError("图片无法解码或自动放大") from exc

    normalized = output.getvalue()
    if not normalized or len(normalized) > MAX_NORMALIZED_IMAGE_BYTES:
        raise ImageValidationError("自动放大后的图片为空或超过 10MB")
    final_dimensions = image_dimensions(normalized, "image/jpeg")
    return normalized, "image/jpeg", original_dimensions, final_dimensions


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
