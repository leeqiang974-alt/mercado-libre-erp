from io import BytesIO
import struct

from PIL import Image

import pytest

from app.services.image_validation import (
    ImageValidationError,
    ensure_listing_image_size,
    image_dimensions,
    normalize_listing_image,
)


def jpeg(width: int, height: int) -> bytes:
    return b"\xff\xd8" + b"\xff\xc0" + struct.pack(">H", 17) + b"\x08" + struct.pack(">HH", height, width) + b"\x03" + b"\x00" * 10 + b"\xff\xd9"


def png(width: int, height: int) -> bytes:
    return b"\x89PNG\r\n\x1a\n" + struct.pack(">I", 13) + b"IHDR" + struct.pack(">II", width, height)


def test_reads_real_jpeg_and_png_dimensions():
    assert image_dimensions(jpeg(319, 489), "image/jpeg") == (319, 489)
    assert image_dimensions(png(500, 700), "image/png") == (500, 700)


def test_rejects_picture_below_mercado_libre_minimum_edge():
    with pytest.raises(ImageValidationError, match="319×489px"):
        ensure_listing_image_size(jpeg(319, 489), "image/jpeg")


def test_accepts_picture_at_mercado_libre_minimum_edge():
    assert ensure_listing_image_size(jpeg(500, 500), "image/jpeg") == (500, 500)


def valid_jpeg(width: int, height: int) -> bytes:
    image = Image.new("RGB", (width, height), "#4477aa")
    output = BytesIO()
    image.save(output, format="JPEG", quality=90)
    return output.getvalue()


def test_upscales_eligible_image_without_ai():
    data, content_type, original, final = normalize_listing_image(valid_jpeg(250, 400), "image/jpeg")

    assert content_type == "image/jpeg"
    assert original == (250, 400)
    assert final == (500, 800)
    assert ensure_listing_image_size(data, content_type) == (500, 800)


def test_does_not_upscale_icon_sized_source_image():
    with pytest.raises(ImageValidationError, match="小于 100px"):
        normalize_listing_image(valid_jpeg(99, 300), "image/jpeg")


def test_resizes_both_edges_proportionally_for_publish_minimum():
    data, content_type, original, final = normalize_listing_image(valid_jpeg(320, 480), "image/jpeg")

    assert content_type == "image/jpeg"
    assert original == (320, 480)
    assert final == (500, 750)
