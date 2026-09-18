from __future__ import annotations

import asyncio
import logging

from app.collectors.forum import ForumCollector
from app.database.database import SessionLocal
from app.database.repository import save_forum_records
from app.processors.deduplicator import deduplicate_records
from app.processors.normalizer import normalize_workflow_record
from app.processors.validator import validate_workflow_record


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
)

logger = logging.getLogger(__name__)


KEYWORDS = [
    "n8n Gmail automation",
    "n8n Google Sheets automation",
    "n8n WhatsApp automation",
    "n8n Slack automation",
    "n8n Telegram automation",
    "n8n AI agent",
    "n8n lead generation",
    "n8n web scraping",
    "n8n CRM automation",
    "n8n email automation",
]


async def collect_forum() -> None:

    collector = ForumCollector()

    all_records = []

    for keyword in KEYWORDS:

        logger.info(
            "Collecting Forum data for keyword: %s",
            keyword,
        )

        try:

            records = await collector.collect(
                query=keyword,
                max_pages_per_query=1,
            )

            for record in records:

                is_valid, errors = (
                    validate_workflow_record(record)
                )

                if not is_valid:

                    logger.warning(
                        "Rejected forum record %s: %s",
                        record.get("topic_id"),
                        errors,
                    )

                    continue

                normalized = (
                    normalize_workflow_record(record)
                )

                all_records.append(normalized)

        except Exception:

            logger.exception(
                "Forum collection failed for keyword: %s",
                keyword,
            )

    logger.info(
        "Total Forum records before deduplication: %d",
        len(all_records),
    )

    unique_records = deduplicate_records(
        all_records
    )

    logger.info(
        "Forum records after deduplication: %d",
        len(unique_records),
    )

    db = SessionLocal()

    try:

        stored = save_forum_records(
            db=db,
            records=unique_records,
        )

        logger.info(
            "Successfully stored %d Forum records",
            stored,
        )

    finally:

        db.close()


if __name__ == "__main__":
    asyncio.run(collect_forum())