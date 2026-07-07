import argparse
import asyncio
import time

from app.db.session import SessionLocal
from app.workers.collection_worker import run_pending_collection_jobs
from app.workers.publish_worker import run_pending_publish_jobs


def main() -> None:
    parser = argparse.ArgumentParser(description="Run background jobs.")
    parser.add_argument(
        "--queue",
        choices=["collection", "publish"],
        default="collection",
        help="Queue to process.",
    )
    parser.add_argument("--limit", type=int, default=10, help="Maximum pending jobs per pass.")
    parser.add_argument("--loop", action="store_true", help="Keep polling for pending jobs.")
    parser.add_argument("--interval", type=float, default=30.0, help="Polling interval in seconds.")
    args = parser.parse_args()

    while True:
        with SessionLocal() as db:
            if args.queue == "publish":
                summary = asyncio.run(run_pending_publish_jobs(db, limit=args.limit))
            else:
                summary = asyncio.run(run_pending_collection_jobs(db, limit=args.limit))
        print(summary, flush=True)
        if not args.loop:
            return
        time.sleep(args.interval)


if __name__ == "__main__":
    main()
