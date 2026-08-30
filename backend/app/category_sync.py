"""Run the global CBT bilingual category catalog synchronizer."""

import argparse
import asyncio

from app.api.routes.stores import create_meli_client, create_oauth_client
from app.core.config import get_settings
from app.db.session import SessionLocal
from app.models.store import Store
from app.services.meli.category_catalog import sync_category_catalog
from app.services.meli.token_vault import resolve_fresh_store_access_token


async def run(store_id: int) -> None:
    settings = get_settings()
    with SessionLocal() as db:
        store = db.get(Store, store_id)
        if store is None or store.site_id.strip().upper() != "CBT":
            raise RuntimeError("A connected CBT store is required.")
        token = await resolve_fresh_store_access_token(
            db=db,
            store=store,
            encryption_key=settings.token_encryption_key,
            oauth_client=create_oauth_client(db),
        )
        if not token:
            raise RuntimeError("Store access token is unavailable.")
        payload = await sync_category_catalog(
            db,
            create_meli_client(token),
            "CBT",
            settings.deepseek_api_key,
            settings.deepseek_base_url,
            settings.deepseek_model,
        )
        print({
            "site": "CBT",
            "nodes": len(payload["nodes"]),
            "complete": payload["complete"],
            "translation_version": payload["translation_version"],
            "translated_by": payload["translated_by"],
        }, flush=True)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--store-id", type=int, required=True)
    args = parser.parse_args()
    asyncio.run(run(args.store_id))


if __name__ == "__main__":
    main()
