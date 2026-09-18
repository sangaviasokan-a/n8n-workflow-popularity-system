from __future__ import annotations

import asyncio
import logging

from app.collectors.youtube import YouTubeCollector
from app.database.database import SessionLocal
from app.database.repository import save_youtube_records
from app.processors.deduplicator import deduplicate_records
from app.processors.normalizer import normalize_workflow_record
from app.processors.validator import validate_workflow_record


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
)

logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)

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


async def collect_youtube() -> None:
    collector = YouTubeCollector()

    all_records = []

    for keyword in KEYWORDS:
        logger.info(
            "Collecting YouTube data for keyword: %s",
            keyword,
        )

        try:
            records = await collector.collect(
                keyword=keyword,
                max_results=10,
            )

            for record in records:
                is_valid, errors = validate_workflow_record(record)

                if not is_valid:
                    logger.warning(
                        "Rejected record %s: %s",
                        record.get("video_id"),
                        errors,
                    )
                    continue

                normalized = normalize_workflow_record(record)

                all_records.append(normalized)

        except Exception:
            logger.exception(
                "YouTube collection failed for keyword: %s",
                keyword,
            )

    logger.info(
        "Total records collected before deduplication: %d",
        len(all_records),
    )

    unique_records = deduplicate_records(all_records)

    logger.info(
        "Records after deduplication: %d",
        len(unique_records),
    )

    db = SessionLocal()

    try:
        stored = save_youtube_records(
            db=db,
            records=unique_records,
        )

        logger.info(
            "Successfully stored %d YouTube records",
            stored,
        )

    finally:
        db.close()


if __name__ == "__main__":
    asyncio.run(collect_youtube())