"""Fill missing Chinese labels in the completed CBT category catalog."""

import argparse
import asyncio

from app.core.config import get_settings
from app.db.session import SessionLocal
from app.services.meli.category_catalog import complete_category_catalog_translations


async def run(site_id: str) -> None:
    settings = get_settings()
    with SessionLocal() as db:
        result = await complete_category_catalog_translations(
            db, site_id, settings.deepseek_api_key,
            settings.deepseek_base_url, settings.deepseek_model,
        )
        print(result, flush=True)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--site-id", default="CBT")
    args = parser.parse_args()
    asyncio.run(run(args.site_id))


if __name__ == "__main__":
    main()
