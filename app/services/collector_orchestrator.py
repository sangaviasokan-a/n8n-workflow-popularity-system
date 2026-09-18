from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

from sqlalchemy.orm import Session

from app.collectors.forum import ForumCollector
from app.collectors.google_trends import GoogleTrendsCollector
from app.collectors.queries import (
    FORUM_WORKFLOW_QUERIES,
    GOOGLE_TRENDS_KEYWORDS,
    YOUTUBE_WORKFLOW_QUERIES,
)
from app.collectors.youtube import YouTubeCollector
from app.database.repository import (
    save_forum_records,
    save_google_trends_records,
    save_youtube_records,
)
from app.processors.deduplicator import Deduplicator
from app.processors.normalizer import normalize_record
from app.processors.validator import validate_record

logger = logging.getLogger(__name__)


@dataclass
class PlatformResult:
    """
    Collection result for one platform.
    """

    collected: int = 0
    valid: int = 0
    rejected: int = 0
    duplicates_removed: int = 0
    stored: int = 0
    error: str | None = None
    records: list[dict[str, Any]] = field(
        default_factory=list
    )


class CollectionOrchestrator:
    """
    Coordinates workflow collection from all supported platforms.

    Supported platforms:
        - YouTube
        - n8n Forum
        - Google Trends
    """

    def __init__(
        self,
        youtube_collector: YouTubeCollector | None = None,
        forum_collector: ForumCollector | None = None,
        google_collector: GoogleTrendsCollector | None = None,
    ) -> None:

        self.youtube = (
            youtube_collector
            or YouTubeCollector()
        )

        self.forum = (
            forum_collector
            or ForumCollector()
        )

        self.google = (
            google_collector
            or GoogleTrendsCollector(
                request_delay=3.0
            )
        )

        self.deduplicator = Deduplicator()

    # ------------------------------------------------------------------
    # Validation
    # ------------------------------------------------------------------

    @staticmethod
    def _validate_records(
        records: list[dict[str, Any]],
    ) -> tuple[
        list[dict[str, Any]],
        int,
    ]:
        """
        Validate records and return:

            (valid_records, rejected_count)
        """

        valid_records: list[dict[str, Any]] = []
        rejected = 0

        for record in records:

            try:
                result = validate_record(record)

                if result:
                    valid_records.append(record)
                else:
                    rejected += 1

            except Exception:
                rejected += 1

                logger.warning(
                    "Record validation failed",
                    extra={
                        "platform": record.get(
                            "platform"
                        ),
                        "source_id": record.get(
                            "source_id"
                        ),
                    },
                    exc_info=True,
                )

        return valid_records, rejected

    # ------------------------------------------------------------------
    # Normalization
    # ------------------------------------------------------------------

    @staticmethod
    def _normalize_records(
        records: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        """
        Normalize records before persistence.
        """

        normalized: list[dict[str, Any]] = []

        for record in records:

            try:
                normalized_record = normalize_record(
                    record
                )

                normalized.append(
                    normalized_record
                )

            except Exception:
                logger.warning(
                    "Record normalization failed",
                    extra={
                        "platform": record.get(
                            "platform"
                        ),
                        "source_id": record.get(
                            "source_id"
                        ),
                    },
                    exc_info=True,
                )

        return normalized

    # ------------------------------------------------------------------
    # Deduplication
    # ------------------------------------------------------------------

    def _deduplicate_records(
        self,
        records: list[dict[str, Any]],
    ) -> tuple[
        list[dict[str, Any]],
        int,
    ]:
        """
        Remove duplicate records.

        Deduplication is performed independently
        inside the supplied collection.
        """

        if not records:
            return [], 0

        before = len(records)

        try:
            unique_records = (
                self.deduplicator.deduplicate(
                    records
                )
            )

        except Exception:
            logger.warning(
                "Deduplication failed; retaining records",
                exc_info=True,
            )

            return records, 0

        removed = max(
            0,
            before - len(unique_records),
        )

        return unique_records, removed

    # ------------------------------------------------------------------
    # YouTube
    # ------------------------------------------------------------------

    async def _collect_youtube(
        self,
        db: Session,
    ) -> PlatformResult:

        result = PlatformResult()

        try:

            logger.info(
                "Starting YouTube collection"
            )

            records = await self.youtube.collect(
                queries=YOUTUBE_WORKFLOW_QUERIES,
                max_results_per_query=10,
            )

            result.collected = len(records)

            logger.info(
                "YouTube raw collection completed",
                extra={
                    "records": len(records)
                },
            )

            valid_records, rejected = (
                self._validate_records(records)
            )

            result.valid = len(valid_records)
            result.rejected = rejected

            normalized_records = (
                self._normalize_records(
                    valid_records
                )
            )

            unique_records, duplicates = (
                self._deduplicate_records(
                    normalized_records
                )
            )

            result.duplicates_removed = (
                duplicates
            )

            result.records = unique_records

            if unique_records:

                result.stored = (
                    save_youtube_records(
                        db,
                        unique_records,
                    )
                )

            logger.info(
                "YouTube processing completed",
                extra={
                    "collected": result.collected,
                    "valid": result.valid,
                    "rejected": result.rejected,
                    "duplicates_removed": (
                        result.duplicates_removed
                    ),
                    "stored": result.stored,
                },
            )

        except Exception as exc:

            result.error = str(exc)

            logger.error(
                "YouTube collection failed",
                extra={
                    "error": str(exc)
                },
                exc_info=True,
            )

        return result

    # ------------------------------------------------------------------
    # Forum
    # ------------------------------------------------------------------

    async def _collect_forum(
        self,
        db: Session,
    ) -> PlatformResult:

        result = PlatformResult()

        try:

            logger.info(
                "Starting n8n Forum collection"
            )

            records = await self.forum.collect(
                queries=FORUM_WORKFLOW_QUERIES,
                max_pages_per_query=1,
            )

            result.collected = len(records)

            logger.info(
                "Forum raw collection completed",
                extra={
                    "records": len(records)
                },
            )

            valid_records, rejected = (
                self._validate_records(records)
            )

            result.valid = len(valid_records)
            result.rejected = rejected

            normalized_records = (
                self._normalize_records(
                    valid_records
                )
            )

            unique_records, duplicates = (
                self._deduplicate_records(
                    normalized_records
                )
            )

            result.duplicates_removed = (
                duplicates
            )

            result.records = unique_records

            if unique_records:

                result.stored = (
                    save_forum_records(
                        db,
                        unique_records,
                    )
                )

            logger.info(
                "Forum processing completed",
                extra={
                    "collected": result.collected,
                    "valid": result.valid,
                    "rejected": result.rejected,
                    "duplicates_removed": (
                        result.duplicates_removed
                    ),
                    "stored": result.stored,
                },
            )

        except Exception as exc:

            result.error = str(exc)

            logger.error(
                "Forum collection failed",
                extra={
                    "error": str(exc)
                },
                exc_info=True,
            )

        return result

    # ------------------------------------------------------------------
    # Google Trends
    # ------------------------------------------------------------------

    async def _collect_google(
        self,
        db: Session,
    ) -> PlatformResult:

        result = PlatformResult()

        try:

            logger.info(
                "Starting Google Trends collection"
            )

            records = await self.google.collect(
                keywords=GOOGLE_TRENDS_KEYWORDS,
                countries=["US", "IN"],
                timeframe="today 12-m",
            )

            result.collected = len(records)

            logger.info(
                "Google Trends raw collection completed",
                extra={
                    "records": len(records)
                },
            )

            valid_records, rejected = (
                self._validate_records(records)
            )

            result.valid = len(valid_records)
            result.rejected = rejected

            normalized_records = (
                self._normalize_records(
                    valid_records
                )
            )

            unique_records, duplicates = (
                self._deduplicate_records(
                    normalized_records
                )
            )

            result.duplicates_removed = (
                duplicates
            )

            result.records = unique_records

            if unique_records:

                result.stored = (
                    save_google_trends_records(
                        db,
                        unique_records,
                    )
                )

            logger.info(
                "Google Trends processing completed",
                extra={
                    "collected": result.collected,
                    "valid": result.valid,
                    "rejected": result.rejected,
                    "duplicates_removed": (
                        result.duplicates_removed
                    ),
                    "stored": result.stored,
                },
            )

        except Exception as exc:

            result.error = str(exc)

            logger.error(
                "Google Trends collection failed",
                extra={
                    "error": str(exc)
                },
                exc_info=True,
            )

        return result

    # ------------------------------------------------------------------
    # Public platform collection methods
    # ------------------------------------------------------------------

    async def collect_youtube(
        self,
        db: Session,
    ) -> PlatformResult:
        """
        Public entry point for YouTube collection.
        """

        logger.info(
            "Public YouTube collection requested"
        )

        return await self._collect_youtube(db)

    async def collect_forum(
        self,
        db: Session,
    ) -> PlatformResult:
        """
        Public entry point for n8n Forum collection.
        """

        logger.info(
            "Public Forum collection requested"
        )

        return await self._collect_forum(db)

    async def collect_google(
        self,
        db: Session,
    ) -> PlatformResult:
        """
        Public entry point for Google Trends collection.
        """

        logger.info(
            "Public Google Trends collection requested"
        )

        return await self._collect_google(db)

    # ------------------------------------------------------------------
    # Complete collection
    # ------------------------------------------------------------------

    async def run(
        self,
        db: Session,
    ) -> dict[str, Any]:

        logger.info(
            "=================================================="
        )

        logger.info(
            "Starting complete workflow collection"
        )

        logger.info(
            "=================================================="
        )

        # --------------------------------------------------------------
        # Each source is isolated.
        # --------------------------------------------------------------

        youtube_result = await self._collect_youtube(
            db
        )

        forum_result = await self._collect_forum(
            db
        )

        google_result = await self._collect_google(
            db
        )

        # --------------------------------------------------------------
        # Totals
        # --------------------------------------------------------------

        results = {
            "youtube": youtube_result,
            "forum": forum_result,
            "google": google_result,
        }

        total_collected = sum(
            item.collected
            for item in results.values()
        )

        total_valid = sum(
            item.valid
            for item in results.values()
        )

        total_rejected = sum(
            item.rejected
            for item in results.values()
        )

        total_duplicates = sum(
            item.duplicates_removed
            for item in results.values()
        )

        total_stored = sum(
            item.stored
            for item in results.values()
        )

        failed_platforms = [
            platform
            for platform, item in results.items()
            if item.error
        ]

        successful_platforms = [
            platform
            for platform, item in results.items()
            if not item.error
        ]

        # --------------------------------------------------------------
        # Overall status
        # --------------------------------------------------------------

        if len(successful_platforms) == 3:
            status = "completed"

        elif successful_platforms:
            status = "partial"

        else:
            status = "failed"

        summary = {
            "status": status,
            "total_collected": total_collected,
            "total_valid": total_valid,
            "total_rejected": total_rejected,
            "total_duplicates_removed": (
                total_duplicates
            ),
            "total_stored": total_stored,
            "successful_platforms": (
                successful_platforms
            ),
            "failed_platforms": (
                failed_platforms
            ),
            "platforms": {
                "youtube": {
                    "collected": youtube_result.collected,
                    "valid": youtube_result.valid,
                    "rejected": youtube_result.rejected,
                    "duplicates_removed": (
                        youtube_result.duplicates_removed
                    ),
                    "stored": youtube_result.stored,
                    "error": youtube_result.error,
                },
                "forum": {
                    "collected": forum_result.collected,
                    "valid": forum_result.valid,
                    "rejected": forum_result.rejected,
                    "duplicates_removed": (
                        forum_result.duplicates_removed
                    ),
                    "stored": forum_result.stored,
                    "error": forum_result.error,
                },
                "google": {
                    "collected": google_result.collected,
                    "valid": google_result.valid,
                    "rejected": google_result.rejected,
                    "duplicates_removed": (
                        google_result.duplicates_removed
                    ),
                    "stored": google_result.stored,
                    "error": google_result.error,
                },
            },
        }

        logger.info(
            "Complete workflow collection finished",
            extra={
                "status": status,
                "total_collected": total_collected,
                "total_valid": total_valid,
                "total_rejected": total_rejected,
                "total_stored": total_stored,
                "failed_platforms": failed_platforms,
            },
        )

        return summary