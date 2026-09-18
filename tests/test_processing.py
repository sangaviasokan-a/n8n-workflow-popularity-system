from app.processors.deduplicator import deduplicate_records
from app.processors.normalizer import (
    normalize_workflow_record,
    normalize_workflow_title,
)
from app.processors.scorer import (
    calculate_confidence_score,
    calculate_cross_platform_score,
    calculate_engagement_score,
    calculate_forum_score,
    calculate_google_score,
    calculate_youtube_score,
    log_normalize,
    min_max_normalize,
)
from app.processors.validator import validate_workflow_record


def test_valid_workflow_record():
    record = {
        "platform": "youtube",
        "video_id": "abc123",
        "title": "n8n Gmail Automation",
        "url": "https://youtube.com/watch?v=abc123",
        "views": 1000,
        "likes": 100,
        "comments": 20,
    }

    valid, errors = validate_workflow_record(record)

    assert valid is True
    assert errors == []


def test_invalid_workflow_record():
    record = {
        "platform": "youtube",
        "video_id": "abc123",
        "title": "",
        "url": "invalid",
        "views": -100,
    }

    valid, errors = validate_workflow_record(record)

    assert valid is False
    assert "missing_title" in errors
    assert "invalid_url" in errors
    assert "negative_views" in errors


def test_title_normalization():
    title = "How To: Build Gmail & n8n Automation!"

    result = normalize_workflow_title(title)

    assert result == "build gmail n8n"


def test_record_normalization():
    record = {
        "platform": "YouTube",
        "title": "Gmail & n8n Automation!",
        "country": "in",
    }

    result = normalize_workflow_record(record)

    assert result["platform"] == "youtube"
    assert result["country"] == "IN"
    assert result["normalized_title"] == "gmail n8n"


def test_deduplication():
    records = [
        {
            "platform": "youtube",
            "video_id": "abc123",
            "title": "Workflow 1",
        },
        {
            "platform": "youtube",
            "video_id": "abc123",
            "title": "Workflow 1 duplicate",
        },
        {
            "platform": "youtube",
            "video_id": "xyz789",
            "title": "Workflow 2",
        },
    ]

    result = deduplicate_records(records)

    assert len(result) == 2


def test_log_normalization():
    assert log_normalize(0, 1000) == 0
    assert 0 < log_normalize(100, 1000) < 100
    assert log_normalize(1000, 1000) == 100


def test_min_max_normalization():
    assert min_max_normalize(0, 0, 100) == 0
    assert min_max_normalize(50, 0, 100) == 50
    assert min_max_normalize(100, 0, 100) == 100


def test_engagement_score():
    score = calculate_engagement_score(
        likes_per_view=0.05,
        comments_per_view=0.01,
    )

    assert 0 <= score <= 100


def test_youtube_score():
    score = calculate_youtube_score(
        views_score=80,
        likes_score=70,
        comments_score=60,
        engagement_score=90,
    )

    assert score == 75.5


def test_forum_score():
    score = calculate_forum_score(
        views_score=80,
        replies_score=70,
        likes_score=60,
        contributors_score=50,
    )

    assert score == 68.5


def test_google_score():
    score = calculate_google_score(
        search_interest_score=80,
        trend_growth_score=60,
    )

    assert score == 72.0


def test_confidence_score():
    score = calculate_confidence_score(
        evidence_count=5,
        platform_count=3,
        data_completeness=1.0,
    )

    assert score == 100.0


def test_cross_platform_score():
    score = calculate_cross_platform_score(
        {
            "youtube": 82,
            "forum": 74,
        }
    )

    assert score == 78.57


def test_cross_platform_score_all_platforms():
    score = calculate_cross_platform_score(
        {
            "youtube": 80,
            "forum": 70,
            "google": 60,
        }
    )

    # 80 * 0.40 + 70 * 0.30 + 60 * 0.30 = 71
    assert score == 71.0
