from __future__ import annotations

import logging

from app.collectors.trends import GoogleTrendsCollector
from app.database.database import SessionLocal
from app.database.repository import save_google_trends_records
from app.processors.deduplicator import deduplicate_records
from app.processors.normalizer import normalize_workflow_record
from app.processors.validator import validate_workflow_record


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)

logger = logging.getLogger(__name__)


KEYWORDS = [
    "n8n Gmail automation",
    "n8n Google Sheets",
    "n8n WhatsApp automation",
    "n8n Slack automation",
    "n8n Telegram automation",
    "n8n LinkedIn automation",
    "n8n AI agent",
    "n8n chatbot",
    "n8n lead generation",
    "n8n web scraping",
]


def main() -> None:
    collector = GoogleTrendsCollector()

    raw_records = []

    logger.info(
        "google_collection_started",
        extra={"keyword_count": len(KEYWORDS)},
    )

    # Collect Google Trends data for US and India
    for keyword in KEYWORDS:
        for country in ("US", "IN"):
            record = collector.collect_keyword(
                keyword=keyword,
                country=country,
            )

            if record:
                raw_records.append(record)

    logger.info(
        "google_collection_raw_completed",
        extra={"raw_count": len(raw_records)},
    )

    # Validate
    valid_records = []

    for record in raw_records:
        is_valid, errors = validate_workflow_record(record)

        if is_valid:
            valid_records.append(record)
        else:
            logger.warning(
                "google_record_rejected",
                extra={
                    "keyword": record.get("keyword"),
                    "country": record.get("country"),
                    "errors": errors,
                },
            )

    logger.info(
        "google_validation_completed",
        extra={
            "raw_count": len(raw_records),
            "valid_count": len(valid_records),
            "rejected_count": len(raw_records) - len(valid_records),
        },
    )

    # Normalize
    normalized_records = [
        normalize_workflow_record(record)
        for record in valid_records
    ]

    # Deduplicate
    unique_records = deduplicate_records(normalized_records)

    logger.info(
        "google_deduplication_completed",
        extra={
            "before": len(normalized_records),
            "after": len(unique_records),
            "duplicates_removed": len(normalized_records) - len(unique_records),
        },
    )

    if not unique_records:
        logger.warning("google_no_records_to_store")
        return

    # Store in PostgreSQL
    db = SessionLocal()

    try:
        stored_count = save_google_trends_records(
            db,
            unique_records,
        )

        logger.info(
            "google_database_storage_completed",
            extra={"stored_count": stored_count},
        )

    finally:
        db.close()

    logger.info("google_collection_pipeline_completed")


if __name__ == "__main__":
    main()