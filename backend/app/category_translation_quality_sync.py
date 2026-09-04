"""Repair partially translated Chinese labels in the global CBT catalog."""

import argparse
import asyncio

from app.core.config import get_settings
from app.db.session import SessionLocal
from app.services.meli.category_catalog import improve_category_catalog_translation_quality


async def run(site_id: str) -> None:
    settings = get_settings()
    with SessionLocal() as db:
        result = await improve_category_catalog_translation_quality(
            db, site_id, settings.agnes_api_key,
            settings.agnes_base_url, settings.agnes_model,
        )
        print(result, flush=True)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--site-id", default="CBT")
    args = parser.parse_args()
    asyncio.run(run(args.site_id))


if __name__ == "__main__":
    main()
