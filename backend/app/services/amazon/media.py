import re
from urllib.parse import urlsplit, urlunsplit

from app.schemas.drafts import MARKETING_TERMS


AMAZON_RENDER_SIZE_PATTERN = re.compile(
    r"\._AC(?:_[A-Z]+\d*)*_(?=\.[A-Za-z0-9]+(?:$|[?#]))",
    re.IGNORECASE,
)
AMAZON_GENERIC_RENDER_SIZE_PATTERN = re.compile(
    r"\._[^/?.]+_(?=\.(?:jpe?g|png|webp)(?:$|[?#]))",
    re.IGNORECASE,
)
AMAZON_RENDER_DIMENSION_PATTERN = re.compile(
    r"\._AC_(?:SL|SX|SY|US|SS|SR)(\d+)_",
    re.IGNORECASE,
)
AMAZON_GENERIC_RENDER_DIMENSION_PATTERN = re.compile(
    r"\._(?:SL|SX|SY|US|SS|SR)(\d+)_",
    re.IGNORECASE,
)
MIN_RESIZABLE_SOURCE_IMAGE_EDGE = 100


def _image_identity(url: str) -> str:
    parts = urlsplit(url.strip())
    normalized_path = AMAZON_RENDER_SIZE_PATTERN.sub("", parts.path)
    # The non-AC form (``._SX342_``) is used by responsive Amazon carousels.
    # It must collapse to the same source identity as the large image.
    if "amazon." in parts.netloc.lower():
        normalized_path = AMAZON_GENERIC_RENDER_SIZE_PATTERN.sub("", normalized_path)
    return urlunsplit((parts.scheme.lower(), parts.netloc.lower(), normalized_path, "", ""))


def _image_resolution(url: str) -> int:
    match = AMAZON_RENDER_DIMENSION_PATTERN.search(url)
    if match is None and "amazon." in urlsplit(url).netloc.lower():
        match = AMAZON_GENERIC_RENDER_DIMENSION_PATTERN.search(url)
    return int(match.group(1)) if match else 10_000


def select_listing_images(image_urls: list[object], limit: int = 12) -> list[str]:
    """Keep one highest-resolution URL per Amazon source image."""
    selected: dict[str, tuple[int, int, str]] = {}
    for index, raw_url in enumerate(image_urls):
        url = str(raw_url or "").strip()
        if not url.startswith(("https://", "http://")):
            continue
        resolution = _image_resolution(url)
        # Amazon carousel thumbnails such as _AC_US100_ are navigation assets,
        # not listing media. Keep unknown-size originals and reject only known
        # icon-size renders; eligible 100-499 px images are locally upscaled
        # while mirroring to OSS before they can reach a publish payload.
        if resolution < MIN_RESIZABLE_SOURCE_IMAGE_EDGE:
            continue
        identity = _image_identity(url)
        candidate = (resolution, -index, url)
        existing = selected.get(identity)
        if existing is None or candidate[:2] > existing[:2]:
            selected[identity] = candidate
    return [candidate[2] for candidate in selected.values()][:limit]


def select_product_video_urls(video_urls: list[object], limit: int = 3) -> list[str]:
    """Keep only Amazon VSE delivery URLs captured from the product gallery."""
    selected: list[str] = []
    seen: set[str] = set()
    for raw_url in video_urls:
        url = str(raw_url or "").strip()
        parts = urlsplit(url)
        host = parts.netloc.lower()
        path = parts.path.lower()
        if (
            parts.scheme not in {"http", "https"}
            or host != "m.media-amazon.com"
            or "vse" not in path
            or not path.endswith((".mp4", ".m3u8"))
            or url in seen
        ):
            continue
        seen.add(url)
        selected.append(url)
        if len(selected) >= limit:
            break
    return selected

def prepare_listing_title(source_title: object, source_brand: str) -> str:
    title = " ".join(str(source_title or "").split())
    if source_brand.strip():
        title = re.sub(
            rf"(?<![A-Za-z0-9]){re.escape(source_brand.strip())}(?![A-Za-z0-9])",
            "",
            title,
            flags=re.IGNORECASE,
        )
    for term in MARKETING_TERMS:
        title = re.sub(
            rf"(?<![A-Za-z0-9]){re.escape(term)}(?![A-Za-z0-9])",
            "",
            title,
            flags=re.IGNORECASE,
        )
    return " ".join(title.split()).strip(" -,:;")[:60].rstrip()
