from __future__ import annotations

import logging
from datetime import datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Metric, Source, Workflow
from app.processors.scorer import (
    calculate_confidence_score,
    calculate_cross_platform_score,
    calculate_engagement_score,
    calculate_forum_score,
    calculate_google_score,
    calculate_youtube_score,
    growth_to_score,
    normalize_batch,
)
from app.processors.workflow_matcher import (
    build_workflow_key,
    find_best_workflow_match,
)

logger = logging.getLogger(__name__)


# ============================================================
# SAFE CONVERSION HELPERS
# ============================================================


def _safe_int(
    value: Any,
) -> int | None:
    """
    Convert a value to a non-negative integer.

    Data semantics:

        None
            Metric was unavailable.

        0
            Metric was actually zero.

    Invalid values are treated as unavailable and therefore
    returned as None.
    """

    if value is None:
        return None

    try:
        return max(
            0,
            int(value),
        )

    except (
        TypeError,
        ValueError,
    ):
        return None


def _safe_float(
    value: Any,
) -> float | None:
    """
    Convert a value to float.

    Data semantics:

        None
            Metric was unavailable.

        0
            Metric was actually zero.

    Invalid values are returned as None.
    """

    if value is None:
        return None

    try:
        return float(value)

    except (
        TypeError,
        ValueError,
    ):
        return None


def _parse_datetime(
    value: Any,
) -> datetime | None:
    """
    Safely parse an ISO datetime value.

    Supports:

        - datetime objects
        - ISO strings
        - strings ending with Z
    """

    if value is None:
        return None

    if isinstance(
        value,
        datetime,
    ):
        return value

    if isinstance(
        value,
        str,
    ):
        try:
            return datetime.fromisoformat(
                value.replace(
                    "Z",
                    "+00:00",
                )
            )

        except ValueError:
            return None

    return None


# ============================================================
# WORKFLOW
# ============================================================


def _get_or_create_workflow(
    db: Session,
    record: dict[str, Any],
    workflow_cache: dict[str, Workflow] | None = None,
) -> Workflow:
    """
    Resolve a record to one canonical workflow across platforms.

    Exact canonical keys are preferred.

    If an exact key is not present, the shared workflow matcher
    performs a conservative semantic match.

    Example:

        Build an n8n AI Agent

        AI Agent n8n Tutorial

    can resolve to the same workflow.

    Unrelated integrations such as Gmail and WhatsApp remain
    separate.
    """

    title = str(
        record.get("title")
        or record.get("keyword")
        or ""
    ).strip()

    workflow_key = str(
        record.get("workflow_key")
        or build_workflow_key(title)
    ).strip()

    normalized_title = str(
        record.get("normalized_title")
        or workflow_key
    ).strip()

    if not workflow_key:
        raise ValueError(
            "Unable to generate workflow_key."
        )

    # --------------------------------------------------------
    # Exact canonical key match
    # --------------------------------------------------------

    if workflow_cache is not None:
        workflow = workflow_cache.get(workflow_key)
    else:
        workflow = db.scalar(
            select(Workflow)
            .where(
                Workflow.workflow_key
                == workflow_key
            )
            .limit(1)
        )

    if workflow:

        if (
            not workflow.description
            and record.get("description")
        ):
            workflow.description = str(
                record["description"]
            )

        return workflow

    # --------------------------------------------------------
    # Conservative fuzzy resolution
    # --------------------------------------------------------

    if workflow_cache is not None:
        candidates = list(workflow_cache.values())
    else:
        candidates = db.scalars(
            select(Workflow)
        ).all()

    incoming_platform = (
        str(
            record.get("platform")
            or ""
        )
        .lower()
        .strip()
        or None
    )

    workflow, score = find_best_workflow_match(
        candidates,
        workflow_key,
        incoming_platform,
    )

    if workflow is not None:

        logger.info(
            "workflow_fuzzy_reused | "
            "workflow_id=%s | "
            "incoming_key=%s | "
            "existing_key=%s | "
            "score=%.3f",
            workflow.id,
            workflow_key,
            workflow.workflow_key,
            score,
        )

        if (
            not workflow.description
            and record.get("description")
        ):
            workflow.description = str(
                record["description"]
            )

        if workflow_cache is not None:
            workflow_cache[workflow.workflow_key] = workflow

        return workflow

    # --------------------------------------------------------
    # Create workflow
    # --------------------------------------------------------

    workflow = Workflow(
        title=title or workflow_key,
        normalized_title=normalized_title,
        workflow_key=workflow_key,
        description=record.get(
            "description"
        ),
        country=None,
        popularity_score=0.0,
        confidence_score=0.0,
        evidence_count=0,
    )

    db.add(workflow)
    db.flush()

    if workflow_cache is not None:
        workflow_cache[workflow.workflow_key] = workflow

    return workflow


# ============================================================
# SOURCE
# ============================================================


def _get_or_create_source(
    db: Session,
    workflow: Workflow,
    record: dict[str, Any],
    source_cache: dict[tuple[str, str], Source] | None = None,
) -> Source:
    """
    Find or create a source using:

        platform + source_id

    Country is stored at source/evidence level.

    This is important because Google Trends can provide:

        US evidence

    and:

        IN evidence

    for the same workflow.
    """

    platform = str(
        record.get("platform")
        or ""
    ).lower().strip()

    if not platform:
        raise ValueError(
            "Record does not contain a platform."
        )

    source_id = (
        record.get("source_id")
        or record.get("video_id")
        or record.get("topic_id")
        or record.get("keyword")
    )

    if not source_id:
        raise ValueError(
            "Record does not contain a source identifier."
        )

    source_id = str(
        source_id
    ).strip()

    if not source_id:
        raise ValueError(
            "Source identifier cannot be empty."
        )

    # --------------------------------------------------------
    # Country
    # --------------------------------------------------------

    country = record.get(
        "country"
    )

    if isinstance(
        country,
        str,
    ):
        country = (
            country
            .upper()
            .strip()
        )

    if country not in {
        "US",
        "IN",
    }:
        country = None

    # --------------------------------------------------------
    # Find existing source
    # --------------------------------------------------------

    source_key = (platform, source_id)

    if source_cache is not None:
        source = source_cache.get(source_key)
    else:
        source = db.scalar(
            select(Source)
            .where(
                Source.platform
                == platform
            )
            .where(
                Source.source_id
                == source_id
            )
            .limit(1)
        )

    if source:

        # ----------------------------------------------------
        # Update URL when available
        # ----------------------------------------------------

        if record.get("url"):

            source.url = str(
                record["url"]
            )

        # ----------------------------------------------------
        # Update published date
        # ----------------------------------------------------

        parsed_date = _parse_datetime(
            record.get(
                "published_at"
            )
        )

        if parsed_date:

            source.published_at = (
                parsed_date
            )

        # ----------------------------------------------------
        # Update country only when actual evidence provides it
        # ----------------------------------------------------

        if country:

            source.country = country

        # ----------------------------------------------------
        # Make sure source belongs to canonical workflow
        # ----------------------------------------------------

        if (
            source.workflow_id
            != workflow.id
        ):

            logger.warning(
                "source_workflow_reassigned | "
                "source_id=%s | "
                "platform=%s | "
                "old_workflow_id=%s | "
                "new_workflow_id=%s",
                source_id,
                platform,
                source.workflow_id,
                workflow.id,
            )

            source.workflow_id = (
                workflow.id
            )

        logger.info(
            "source_reused | "
            "source_id=%s | "
            "platform=%s | "
            "workflow_id=%s | "
            "country=%s",
            source_id,
            platform,
            workflow.id,
            country,
        )

        if source_cache is not None:
            source_cache[source_key] = source

        return source

    # --------------------------------------------------------
    # Create new source
    # --------------------------------------------------------

    source = Source(
        workflow_id=workflow.id,
        platform=platform,
        source_id=source_id,
        url=str(
            record.get("url")
            or ""
        ),
        country=country,
        published_at=_parse_datetime(
            record.get(
                "published_at"
            )
        ),
    )

    db.add(source)
    db.flush()

    if source_cache is not None:
        source_cache[source_key] = source

    logger.info(
        "source_created | "
        "source_id=%s | "
        "platform=%s | "
        "workflow_id=%s | "
        "country=%s",
        source_id,
        platform,
        workflow.id,
        country,
    )

    return source


# ============================================================
# METRIC
# ============================================================


def _save_metric(
    db: Session,
    source: Source,
    record: dict[str, Any],
    popularity_score: float,
    confidence_score: float,
) -> Metric:
    """
    Save a historical metric snapshot.

    IMPORTANT DATA SEMANTICS:

        None
            Metric was unavailable.

        0
            Metric was genuinely zero.

    We do NOT convert unavailable values to zero anymore.
    """

    # --------------------------------------------------------
    # Raw metrics
    # --------------------------------------------------------

    views = _safe_int(
        record.get("views")
    )

    likes = _safe_int(
        record.get("likes")
    )

    comments = _safe_int(
        record.get("comments")
    )

    replies = _safe_int(
        record.get("replies")
    )

    contributors = _safe_int(
        record.get("contributors")
    )

    # --------------------------------------------------------
    # Engagement ratios
    # --------------------------------------------------------

    if (
        views is not None
        and views > 0
    ):

        likes_per_view = (
            likes / views
            if likes is not None
            else None
        )

        comments_per_view = (
            comments / views
            if comments is not None
            else None
        )

    else:

        likes_per_view = None
        comments_per_view = None

    # --------------------------------------------------------
    # Google Trends
    # --------------------------------------------------------

    current_interest = _safe_float(
        record.get(
            "current_interest"
        )
    )

    if current_interest is not None:

        search_interest = max(
            0.0,
            min(
                current_interest,
                100.0,
            ),
        )

    else:

        search_interest = None

    average_interest = _safe_float(
        record.get(
            "average_interest"
        )
    )

    if average_interest is not None:

        average_interest = max(
            0.0,
            min(
                average_interest,
                100.0,
            ),
        )

    maximum_interest = _safe_float(
        record.get(
            "maximum_interest"
        )
    )

    if maximum_interest is not None:

        maximum_interest = max(
            0.0,
            min(
                maximum_interest,
                100.0,
            ),
        )

    trend_growth = _safe_float(
        record.get(
            "trend_growth"
        )
    )

    # --------------------------------------------------------
    # Create historical metric
    # --------------------------------------------------------

    metric = Metric(
        source_id=source.id,

        views=views,
        likes=likes,
        comments=comments,
        replies=replies,
        contributors=contributors,

        likes_per_view=likes_per_view,
        comments_per_view=comments_per_view,

        popularity_score=popularity_score,
        confidence_score=confidence_score,

        captured_at=datetime.utcnow(),

        search_interest=search_interest,
        average_interest=average_interest,
        maximum_interest=maximum_interest,
        trend_growth=trend_growth,
    )

    db.add(metric)

    return metric


# ============================================================
# BATCH NORMALIZATION
# ============================================================


def _apply_batch_normalization(
    records: list[dict[str, Any]],
    platform: str,
) -> None:
    """
    Normalize raw platform metrics across the current batch.

    None values are preserved in the source records.

    normalize_batch() treats unavailable values as having zero
    mathematical contribution only for scoring.
    """

    if not records:
        return

    platform = (
        platform
        .lower()
        .strip()
    )

    # ========================================================
    # YOUTUBE
    # ========================================================

    if platform == "youtube":

        views = [
            _safe_int(
                record.get("views")
            )
            for record in records
        ]

        likes = [
            _safe_int(
                record.get("likes")
            )
            for record in records
        ]

        comments = [
            _safe_int(
                record.get("comments")
            )
            for record in records
        ]

        views_scores = normalize_batch(
            views
        )

        likes_scores = normalize_batch(
            likes
        )

        comments_scores = normalize_batch(
            comments
        )

        for index, record in enumerate(
            records
        ):

            record["_views_score"] = (
                views_scores[index]
            )

            record["_likes_score"] = (
                likes_scores[index]
            )

            record["_comments_score"] = (
                comments_scores[index]
            )

        return

    # ========================================================
    # FORUM
    # ========================================================

    if platform == "forum":

        views = [
            _safe_int(
                record.get("views")
            )
            for record in records
        ]

        replies = [
            _safe_int(
                record.get("replies")
            )
            for record in records
        ]

        likes = [
            _safe_int(
                record.get("likes")
            )
            for record in records
        ]

        contributors = [
            _safe_int(
                record.get("contributors")
            )
            for record in records
        ]

        views_scores = normalize_batch(
            views
        )

        replies_scores = normalize_batch(
            replies
        )

        likes_scores = normalize_batch(
            likes
        )

        contributors_scores = normalize_batch(
            contributors
        )

        for index, record in enumerate(
            records
        ):

            record["_views_score"] = (
                views_scores[index]
            )

            record["_replies_score"] = (
                replies_scores[index]
            )

            record["_likes_score"] = (
                likes_scores[index]
            )

            record["_contributors_score"] = (
                contributors_scores[index]
            )

        return

    # ========================================================
    # GOOGLE
    # ========================================================

    if platform == "google":

        for record in records:

            current_interest = _safe_float(
                record.get(
                    "current_interest"
                )
            )

            if current_interest is not None:

                record[
                    "_search_interest_score"
                ] = max(
                    0.0,
                    min(
                        current_interest,
                        100.0,
                    ),
                )

            else:

                record[
                    "_search_interest_score"
                ] = 0.0

        return


# ============================================================
# PLATFORM SCORE
# ============================================================


def _calculate_source_score(
    record: dict[str, Any],
    platform: str,
) -> float:
    """
    Calculate a normalized popularity score for one source.

    Missing raw metrics are treated as zero ONLY inside the
    mathematical scoring calculation.

    The original database value remains NULL.
    """

    platform = (
        platform
        .lower()
        .strip()
    )

    # ========================================================
    # YOUTUBE
    # ========================================================

    if platform == "youtube":

        views = _safe_int(
            record.get("views")
        )

        likes = _safe_int(
            record.get("likes")
        )

        comments = _safe_int(
            record.get("comments")
        )

        views_score = _safe_float(
            record.get(
                "_views_score"
            )
        )

        likes_score = _safe_float(
            record.get(
                "_likes_score"
            )
        )

        comments_score = _safe_float(
            record.get(
                "_comments_score"
            )
        )

        # ----------------------------------------------------
        # For calculations only
        # ----------------------------------------------------

        views_for_score = (
            views
            if views is not None
            else 0
        )

        likes_for_score = (
            likes
            if likes is not None
            else 0
        )

        comments_for_score = (
            comments
            if comments is not None
            else 0
        )

        # ----------------------------------------------------
        # Engagement
        # ----------------------------------------------------

        if views_for_score > 0:

            likes_per_view = (
                likes_for_score
                / views_for_score
            )

            comments_per_view = (
                comments_for_score
                / views_for_score
            )

        else:

            likes_per_view = 0.0
            comments_per_view = 0.0

        engagement_score = (
            calculate_engagement_score(
                likes_per_view,
                comments_per_view,
            )
        )

        return calculate_youtube_score(
            views_score or 0.0,
            likes_score or 0.0,
            comments_score or 0.0,
            engagement_score,
        )

    # ========================================================
    # FORUM
    # ========================================================

    if platform == "forum":

        views_score = _safe_float(
            record.get(
                "_views_score"
            )
        )

        replies_score = _safe_float(
            record.get(
                "_replies_score"
            )
        )

        likes_score = _safe_float(
            record.get(
                "_likes_score"
            )
        )

        contributors_score = _safe_float(
            record.get(
                "_contributors_score"
            )
        )

        return calculate_forum_score(
            views_score or 0.0,
            replies_score or 0.0,
            likes_score or 0.0,
            contributors_score or 0.0,
        )

    # ========================================================
    # GOOGLE TRENDS
    # ========================================================

    if platform == "google":

        raw_search_interest = record.get(
            "_search_interest_score"
        )

        if raw_search_interest is None:

            raw_search_interest = (
                record.get(
                    "current_interest"
                )
            )

        search_interest = _safe_float(
            raw_search_interest
        )

        if search_interest is None:
            search_interest = 0.0

        search_interest = max(
            0.0,
            min(
                search_interest,
                100.0,
            ),
        )

        trend_growth = _safe_float(
            record.get(
                "trend_growth"
            )
        )

        if trend_growth is None:
            trend_growth = 0.0

        trend_growth_score = (
            growth_to_score(
                trend_growth
            )
        )

        return calculate_google_score(
            search_interest,
            trend_growth_score,
        )

    # ========================================================
    # UNKNOWN PLATFORM
    # ========================================================

    logger.warning(
        "unsupported_platform_score | "
        "platform=%s",
        platform,
    )

    return 0.0


# ============================================================
# WORKFLOW SUMMARY
# ============================================================


def _calculate_workflow_summary(
    db: Session,
    workflow: Workflow,
) -> None:
    """
    Recalculate the canonical workflow summary.

    Latest metric from every source is used.

    Cross-platform weights:

        YouTube = 40%
        Forum   = 30%
        Google  = 30%

    Missing platforms are automatically re-weighted.
    """

    platform_scores: dict[
        str,
        list[float],
    ] = {}

    evidence_count = 0

    platform_names: set[str] = set()

    # --------------------------------------------------------
    # Gather latest metric from each source
    # --------------------------------------------------------

    for source in workflow.sources:

        if not source.metrics:
            continue

        latest_metric = max(
            source.metrics,
            key=lambda metric: metric.captured_at,
        )

        platform = (
            source.platform
            .lower()
            .strip()
        )

        platform_names.add(
            platform
        )

        evidence_count += 1

        platform_scores.setdefault(
            platform,
            [],
        ).append(
            latest_metric.popularity_score
        )

    # --------------------------------------------------------
    # Average evidence within platform
    # --------------------------------------------------------

    averaged_platform_scores: dict[
        str,
        float,
    ] = {}

    for platform, scores in (
        platform_scores.items()
    ):

        if scores:

            averaged_platform_scores[
                platform
            ] = (
                sum(scores)
                / len(scores)
            )

    # --------------------------------------------------------
    # Cross-platform popularity
    # --------------------------------------------------------

    workflow.popularity_score = (
        calculate_cross_platform_score(
            averaged_platform_scores
        )
    )

    # --------------------------------------------------------
    # Confidence
    # --------------------------------------------------------

    data_completeness = (
        1.0
        if evidence_count > 0
        else 0.0
    )

    workflow.confidence_score = (
        calculate_confidence_score(
            evidence_count=evidence_count,
            platform_count=len(
                platform_names
            ),
            data_completeness=data_completeness,
        )
    )

    workflow.evidence_count = (
        evidence_count
    )

    logger.info(
        "workflow_summary_updated | "
        "workflow_id=%s | "
        "workflow_key=%s | "
        "popularity=%.2f | "
        "confidence=%.2f | "
        "evidence=%s | "
        "platforms=%s",
        workflow.id,
        workflow.workflow_key,
        workflow.popularity_score,
        workflow.confidence_score,
        workflow.evidence_count,
        sorted(platform_names),
    )


# ============================================================
# COMMON SAVE FUNCTION
# ============================================================


def _save_records(
    db: Session,
    records: list[dict[str, Any]],
    platform: str,
) -> int:
    """
    Shared saving implementation for:

        - YouTube
        - Forum
        - Google Trends

    Pipeline:

        Raw records
            ↓
        Batch normalization
            ↓
        Canonical workflow matching
            ↓
        Source matching
            ↓
        Platform scoring
            ↓
        Historical metric
            ↓
        Workflow summary
            ↓
        PostgreSQL
    """

    if not records:
        return 0

    platform = (
        platform
        .lower()
        .strip()
    )

    supported_platforms = {
        "youtube",
        "forum",
        "google",
    }

    if platform not in supported_platforms:

        raise ValueError(
            f"Unsupported platform: {platform}"
        )

    # --------------------------------------------------------
    # Preload lookup caches for this batch.
    #
    # This is critical on small hosted instances: the previous
    # implementation queried every existing workflow for every
    # record, creating O(records × workflows) database work.
    # --------------------------------------------------------

    workflow_cache = {
        workflow.workflow_key: workflow
        for workflow in db.scalars(
            select(Workflow)
        ).all()
        if workflow.workflow_key
    }

    source_ids = {
        str(
            record.get("source_id")
            or record.get("video_id")
            or record.get("topic_id")
            or record.get("keyword")
            or ""
        ).strip()
        for record in records
    }

    source_ids.discard("")

    source_cache: dict[tuple[str, str], Source] = {}

    if source_ids:
        existing_sources = db.scalars(
            select(Source)
            .where(Source.platform == platform)
            .where(Source.source_id.in_(source_ids))
        ).all()

        source_cache.update(
            {
                (source.platform, source.source_id): source
                for source in existing_sources
            }
        )

    # --------------------------------------------------------
    # Normalize complete batch
    # --------------------------------------------------------

    _apply_batch_normalization(
        records,
        platform,
    )

    stored_count = 0

    workflow_ids: set[int] = set()

    # --------------------------------------------------------
    # Process records
    # --------------------------------------------------------

    for record in records:

        try:

            with db.begin_nested():

                # --------------------------------------------
                # Generate canonical workflow key
                # --------------------------------------------

                title = str(
                    record.get("title")
                    or record.get("keyword")
                    or ""
                ).strip()

                workflow_key = str(
                    record.get(
                        "workflow_key"
                    )
                    or ""
                ).strip()

                if not workflow_key:

                    workflow_key = (
                        build_workflow_key(
                            title
                        )
                    )

                record[
                    "workflow_key"
                ] = workflow_key

                if not workflow_key:

                    raise ValueError(
                        "Unable to generate "
                        "workflow_key for record."
                    )

                # --------------------------------------------
                # Workflow
                # --------------------------------------------

                workflow = (
                    _get_or_create_workflow(
                        db,
                        record,
                        workflow_cache=workflow_cache,
                    )
                )

                workflow_ids.add(
                    workflow.id
                )

                # --------------------------------------------
                # Source
                # --------------------------------------------

                source = (
                    _get_or_create_source(
                        db,
                        workflow,
                        record,
                        source_cache=source_cache,
                    )
                )

                # --------------------------------------------
                # Platform score
                # --------------------------------------------

                score = (
                    _calculate_source_score(
                        record,
                        platform,
                    )
                )

                # --------------------------------------------
                # Evidence confidence
                # --------------------------------------------

                confidence = (
                    calculate_confidence_score(
                        evidence_count=1,
                        platform_count=1,
                        data_completeness=1.0,
                    )
                )

                # --------------------------------------------
                # Historical metric
                # --------------------------------------------

                _save_metric(
                    db,
                    source,
                    record,
                    popularity_score=score,
                    confidence_score=confidence,
                )

                stored_count += 1

        except Exception as exc:

            logger.exception(
                "%s_record_storage_failed | "
                "source_id=%s | "
                "error=%s",
                platform,
                (
                    record.get("source_id")
                    or record.get("video_id")
                    or record.get("topic_id")
                    or record.get("keyword")
                ),
                str(exc),
            )

            # Nested transaction already rolled back the
            # failed record.
            #
            # Do NOT call db.rollback() here because that
            # would rollback successful records too.

            continue

    # --------------------------------------------------------
    # Commit successfully processed records
    # --------------------------------------------------------

    try:

        db.commit()

    except Exception:

        logger.exception(
            "%s_database_commit_failed",
            platform,
        )

        db.rollback()

        raise

    # --------------------------------------------------------
    # Recalculate workflow summaries
    # --------------------------------------------------------

    for workflow_id in workflow_ids:

        workflow = db.get(
            Workflow,
            workflow_id,
        )

        if workflow is None:
            continue

        try:

            _ = workflow.sources

            for source in workflow.sources:
                _ = source.metrics

            _calculate_workflow_summary(
                db,
                workflow,
            )

        except Exception:

            logger.exception(
                "workflow_summary_failed | "
                "workflow_id=%s",
                workflow_id,
            )

    # --------------------------------------------------------
    # Commit summaries
    # --------------------------------------------------------

    try:

        db.commit()

    except Exception:

        logger.exception(
            "%s_workflow_summary_commit_failed",
            platform,
        )

        db.rollback()

        raise

    logger.info(
        "%s_database_storage_completed | "
        "stored_count=%s | "
        "workflow_count=%s",
        platform,
        stored_count,
        len(workflow_ids),
    )

    return stored_count


# ============================================================
# PUBLIC YOUTUBE FUNCTION
# ============================================================


def save_youtube_records(
    db: Session,
    records: list[dict[str, Any]],
) -> int:
    """
    Save YouTube records.
    """

    return _save_records(
        db=db,
        records=records,
        platform="youtube",
    )


# ============================================================
# PUBLIC FORUM FUNCTION
# ============================================================


def save_forum_records(
    db: Session,
    records: list[dict[str, Any]],
) -> int:
    """
    Save Forum records.
    """

    return _save_records(
        db=db,
        records=records,
        platform="forum",
    )


# ============================================================
# PUBLIC GOOGLE TRENDS FUNCTION
# ============================================================


def save_google_trends_records(
    db: Session,
    records: list[dict[str, Any]],
) -> int:
    """
    Save Google Trends records.

    Country is stored at Source.country.

    Example:

        Google US:
            country = US

        Google India:
            country = IN
    """

    return _save_records(
        db=db,
        records=records,
        platform="google",
    )