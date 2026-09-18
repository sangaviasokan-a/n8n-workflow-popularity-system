from __future__ import annotations

from datetime import datetime, timedelta

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from app.database.database import Base
from app.database.repository import (
    save_forum_records,
    save_google_trends_records,
    save_youtube_records,
)
from app.models import Metric, Source, Workflow


# ============================================================
# TEST DATABASE
# ============================================================

@pytest.fixture
def db():
    """
    Create an isolated in-memory SQLite database for repository
    integration tests.

    The repository itself uses SQLAlchemy, so these tests verify
    database/repository behavior without requiring the developer's
    PostgreSQL instance.
    """

    engine = create_engine(
        "sqlite:///:memory:",
        future=True,
    )

    Base.metadata.create_all(engine)

    SessionLocal = sessionmaker(
        bind=engine,
        autoflush=False,
        autocommit=False,
        expire_on_commit=False,
    )

    session = SessionLocal()

    try:
        yield session
    finally:
        session.close()
        engine.dispose()


# ============================================================
# SAMPLE RECORDS
# ============================================================

def youtube_record(
    source_id: str = "youtube-001",
    title: str = "Build an n8n AI Agent Tutorial",
):
    return {
        "platform": "youtube",
        "source_id": source_id,
        "video_id": source_id,
        "title": title,
        "url": f"https://youtube.com/watch?v={source_id}",
        "views": 10000,
        "likes": 500,
        "comments": 100,
        "published_at": "2026-09-10T10:00:00Z",
        "country": "US",
    }


def forum_record(
    source_id: str = "forum-001",
    title: str = "How to create n8n AI Agent",
):
    return {
        "platform": "forum",
        "source_id": source_id,
        "topic_id": source_id,
        "title": title,
        "url": f"https://community.n8n.io/t/{source_id}",
        "views": 5000,
        "likes": 100,
        "replies": 50,
        "contributors": 20,
        "published_at": "2026-09-10T11:00:00Z",
        "country": None,
    }


def google_record(
    source_id: str = "n8n-ai-agent-us",
    title: str = "n8n AI agent",
    country: str = "US",
):
    return {
        "platform": "google",
        "source_id": source_id,
        "title": title,
        "keyword": "n8n AI agent",
        "url": "https://trends.google.com/",
        "current_interest": 85,
        "average_interest": 70,
        "maximum_interest": 100,
        "trend_growth": 15,
        "country": country,
    }


# ============================================================
# CANONICAL WORKFLOW MATCHING
# ============================================================

def test_cross_platform_records_share_one_workflow(
    db,
):
    """
    YouTube, Forum and Google records with semantically equivalent
    titles must resolve to one canonical workflow.
    """

    youtube_count = save_youtube_records(
        db,
        [youtube_record()],
    )

    forum_count = save_forum_records(
        db,
        [forum_record()],
    )

    google_count = save_google_trends_records(
        db,
        [google_record()],
    )

    assert youtube_count == 1
    assert forum_count == 1
    assert google_count == 1

    workflows = db.scalars(
        select(Workflow)
    ).all()

    assert len(workflows) == 1

    workflow = workflows[0]

    assert workflow.workflow_key == "n8n ai agent"

    sources = db.scalars(
        select(Source)
        .where(
            Source.workflow_id == workflow.id
        )
    ).all()

    assert len(sources) == 3

    platforms = {
        source.platform
        for source in sources
    }

    assert platforms == {
        "youtube",
        "forum",
        "google",
    }


# ============================================================
# SOURCE UNIQUENESS
# ============================================================

def test_same_source_does_not_create_duplicate_source(
    db,
):
    """
    Re-collecting the same YouTube source must reuse the existing
    Source rather than creating another Source.
    """

    record = youtube_record(
        source_id="same-video"
    )

    first_count = save_youtube_records(
        db,
        [record],
    )

    second_count = save_youtube_records(
        db,
        [record],
    )

    assert first_count == 1
    assert second_count == 1

    sources = db.scalars(
        select(Source)
        .where(
            Source.platform == "youtube"
        )
    ).all()

    assert len(sources) == 1


# ============================================================
# HISTORICAL METRICS
# ============================================================

def test_recollection_creates_historical_metric(
    db,
):
    """
    A source can be collected multiple times.

    The Source remains the same, while every collection creates
    a new Metric snapshot.
    """

    record = youtube_record(
        source_id="history-video"
    )

    save_youtube_records(
        db,
        [record],
    )

    record["views"] = 20000
    record["likes"] = 1000
    record["comments"] = 200

    save_youtube_records(
        db,
        [record],
    )

    source = db.scalar(
        select(Source)
        .where(
            Source.source_id == "history-video"
        )
    )

    assert source is not None

    metrics = db.scalars(
        select(Metric)
        .where(
            Metric.source_id == source.id
        )
        .order_by(
            Metric.captured_at.asc()
        )
    ).all()

    assert len(metrics) == 2

    assert metrics[0].views == 10000
    assert metrics[1].views == 20000


# ============================================================
# COUNTRY EVIDENCE
# ============================================================

def test_country_is_stored_at_source_level(
    db,
):
    """
    Country belongs to the source/evidence rather than the
    canonical workflow.

    Therefore the same workflow can contain US and IN evidence.
    """

    us = google_record(
        source_id="google-us",
        country="US",
    )

    india = google_record(
        source_id="google-in",
        country="IN",
    )

    save_google_trends_records(
        db,
        [us, india],
    )

    workflows = db.scalars(
        select(Workflow)
    ).all()

    assert len(workflows) == 1

    workflow = workflows[0]

    assert workflow.country is None

    sources = db.scalars(
        select(Source)
        .where(
            Source.workflow_id == workflow.id
        )
        .order_by(Source.source_id)
    ).all()

    assert len(sources) == 2

    countries = {
        source.country
        for source in sources
    }

    assert countries == {
        "US",
        "IN",
    }


# ============================================================
# WORKFLOW SUMMARY
# ============================================================

def test_workflow_summary_is_calculated(
    db,
):
    """
    Saving a record must update the canonical workflow's:

        popularity_score
        confidence_score
        evidence_count
    """

    save_youtube_records(
        db,
        [youtube_record()],
    )

    workflow = db.scalar(
        select(Workflow)
    )

    assert workflow is not None

    assert workflow.evidence_count == 1

    assert (
        workflow.popularity_score >= 0
    )

    assert (
        workflow.popularity_score <= 100
    )

    assert (
        workflow.confidence_score >= 0
    )

    assert (
        workflow.confidence_score <= 100
    )


# ============================================================
# MULTI-PLATFORM SUMMARY
# ============================================================

def test_multi_platform_summary_uses_all_evidence(
    db,
):
    """
    A workflow with YouTube, Forum and Google evidence must
    produce a cross-platform popularity score.
    """

    save_youtube_records(
        db,
        [youtube_record()],
    )

    save_forum_records(
        db,
        [forum_record()],
    )

    save_google_trends_records(
        db,
        [google_record()],
    )

    workflow = db.scalar(
        select(Workflow)
    )

    assert workflow is not None

    assert workflow.evidence_count == 3

    assert (
        workflow.popularity_score > 0
    )

    assert (
        workflow.confidence_score > 0
    )


# ============================================================
# BATCH NORMALIZATION BEHAVIOR
# ============================================================

def test_batch_normalization_produces_different_scores(
    db,
):
    """
    Two YouTube records with different raw metrics should be
    scored relative to their batch rather than both receiving
    identical maximum-normalized metric values.
    """

    records = [
        youtube_record(
            source_id="small-video"
        ),
        youtube_record(
            source_id="large-video"
        ),
    ]

    records[0]["views"] = 1000
    records[0]["likes"] = 50
    records[0]["comments"] = 10

    records[1]["views"] = 100000
    records[1]["likes"] = 5000
    records[1]["comments"] = 1000

    count = save_youtube_records(
        db,
        records,
    )

    assert count == 2

    metrics = db.scalars(
        select(Metric)
        .order_by(
            Metric.id.asc()
        )
    ).all()

    assert len(metrics) == 2

    assert (
        metrics[0].popularity_score
        != metrics[1].popularity_score
    )


# ============================================================
# PARTIAL FAILURE
# ============================================================

def test_bad_record_does_not_rollback_good_records(
    db,
):
    """
    A bad record should not remove successfully processed records.

    This verifies the nested transaction/savepoint behavior in
    repository.py.
    """

    good_record = youtube_record(
        source_id="good-video"
    )

    bad_record = {
        "platform": "youtube",
        "title": "",
        "source_id": "",
        "url": "",
        "views": -100,
        "likes": -10,
        "comments": -5,
    }

    count = save_youtube_records(
        db,
        [
            good_record,
            bad_record,
        ],
    )

    assert count == 1

    sources = db.scalars(
        select(Source)
    ).all()

    assert len(sources) == 1

    assert (
        sources[0].source_id
        == "good-video"
    )


# ============================================================
# GOOGLE TRENDS SCALE
# ============================================================

def test_google_trends_interest_is_limited_to_0_100(
    db,
):
    """
    Google Trends interest should remain within the documented
    0-100 range.
    """

    record = google_record()

    record["current_interest"] = 150
    record["average_interest"] = -20
    record["maximum_interest"] = 500

    save_google_trends_records(
        db,
        [record],
    )

    metric = db.scalar(
        select(Metric)
    )

    assert metric is not None

    assert (
        0 <= metric.search_interest <= 100
    )

    assert (
        0 <= metric.average_interest <= 100
    )

    assert (
        0 <= metric.maximum_interest <= 100
    )


# ============================================================
# PLATFORM SEPARATION
# ============================================================

def test_same_source_id_on_different_platforms_is_allowed(
    db,
):
    """
    source_id uniqueness is scoped by platform.

    Therefore:

        YouTube / 123

    and:

        Forum / 123

    are different sources.
    """

    youtube = youtube_record(
        source_id="123"
    )

    forum = forum_record(
        source_id="123"
    )

    save_youtube_records(
        db,
        [youtube],
    )

    save_forum_records(
        db,
        [forum],
    )

    sources = db.scalars(
        select(Source)
    ).all()

    assert len(sources) == 2

    combinations = {
        (
            source.platform,
            source.source_id,
        )
        for source in sources
    }

    assert combinations == {
        ("youtube", "123"),
        ("forum", "123"),
    }
