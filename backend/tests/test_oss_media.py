import asyncio

from app.core.config import Settings
from app.services.storage import aliyun_oss


def test_oss_mirror_filters_tracking_gif_and_keeps_order(monkeypatch):
    async def fake_mirror(source_url: str, settings: Settings) -> str:
        return f"https://oss.example/{source_url.rsplit('/', 1)[-1]}"

    monkeypatch.setattr(aliyun_oss, "mirror_image_to_oss", fake_mirror)

    mirrored = asyncio.run(
        aliyun_oss.mirror_images_to_oss(
            [
                "https://images.example/one.jpg",
                "https://images.example/grey-pixel.gif",
                "https://images.example/two.png",
                "https://images.example/one.jpg",
            ],
            Settings(),
        )
    )

    assert mirrored == [
        "https://oss.example/one.jpg",
        "https://oss.example/two.png",
        "https://oss.example/one.jpg",
    ]
