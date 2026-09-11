import argparse
import asyncio
import time

from app.db.session import SessionLocal
from app.workers.collection_worker import run_pending_collection_jobs
from app.workers.publish_worker import run_pending_publish_jobs
from app.workers.review_worker import run_pending_review_jobs
from app.workers.ai_content_worker import run_ai_content_prefill_pass


def main() -> None:
    parser = argparse.ArgumentParser(description="Run background jobs.")
    parser.add_argument(
        "--queue",
        choices=["collection", "publish", "review", "ai-content"],
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
            elif args.queue == "review":
                summary = asyncio.run(run_pending_review_jobs(db, limit=args.limit))
            elif args.queue == "ai-content":
                summary = asyncio.run(run_ai_content_prefill_pass(db, limit=min(args.limit, 2)))
            else:
                summary = asyncio.run(run_pending_collection_jobs(db, limit=args.limit))
        print(summary, flush=True)
        if not args.loop:
            return
        time.sleep(1.0 if args.queue == "ai-content" and summary.get("processed", 0) else args.interval)


if __name__ == "__main__":
    main()
