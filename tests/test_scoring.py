from app.processors.scorer import (
    calculate_confidence_score,
    calculate_cross_platform_score,
    calculate_engagement_score,
    calculate_forum_score,
    calculate_google_score,
    calculate_youtube_score,
    growth_to_score,
    log_normalize,
    min_max_normalize,
    normalize_batch,
)


# ============================================================
# NORMALIZATION TESTS
# ============================================================


def test_min_max_normalize():
    assert min_max_normalize(50, 0, 100) == 50.0


def test_min_max_normalize_lower_bound():
    assert min_max_normalize(0, 0, 100) == 0.0


def test_min_max_normalize_upper_bound():
    assert min_max_normalize(100, 0, 100) == 100.0


def test_min_max_normalize_same_range():
    assert min_max_normalize(50, 50, 50) == 50.0


def test_log_normalize_zero():
    assert log_normalize(0, 100) == 0.0


def test_log_normalize_maximum():
    assert log_normalize(100, 100) == 100.0


def test_normalize_batch():
    result = normalize_batch(
        [10, 100, 1000]
    )

    assert len(result) == 3
    assert result[0] < result[1] < result[2]
    assert result[2] == 100.0


def test_normalize_batch_with_none():
    result = normalize_batch(
        [10, None, 100]
    )

    assert len(result) == 3
    assert result[0] > 0
    assert result[1] == 0.0
    assert result[2] == 100.0


def test_normalize_batch_all_none():
    result = normalize_batch(
        [None, None, None]
    )

    assert result == [
        0.0,
        0.0,
        0.0,
    ]


def test_normalize_batch_empty():
    assert normalize_batch([]) == []


# ============================================================
# ENGAGEMENT TESTS
# ============================================================


def test_engagement_score():
    score = calculate_engagement_score(
        0.05,
        0.01,
    )

    assert score == 50.0

def test_engagement_score_zero():
    assert calculate_engagement_score(
        0.0,
        0.0,
    ) == 0.0


def test_engagement_score_caps():
    assert calculate_engagement_score(
        1.0,
        1.0,
    ) == 100.0


# ============================================================
# YOUTUBE TESTS
# ============================================================


def test_youtube_score():
    score = calculate_youtube_score(
        80,
        70,
        60,
        90,
    )

    assert score == 75.5


def test_youtube_score_zero():
    assert calculate_youtube_score(
        0,
        0,
        0,
        0,
    ) == 0.0


def test_youtube_score_maximum():
    assert calculate_youtube_score(
        100,
        100,
        100,
        100,
    ) == 100.0


# ============================================================
# FORUM TESTS
# ============================================================


def test_forum_score():
    score = calculate_forum_score(
        80,
        70,
        60,
        50,
    )

    assert score == 68.5


def test_forum_score_zero():
    assert calculate_forum_score(
        0,
        0,
        0,
        0,
    ) == 0.0


def test_forum_score_maximum():
    assert calculate_forum_score(
        100,
        100,
        100,
        100,
    ) == 100.0


# ============================================================
# GOOGLE TRENDS TESTS
# ============================================================


def test_google_score():
    score = calculate_google_score(
        80,
        60,
    )

    assert score == 72.0


def test_google_score_zero():
    assert calculate_google_score(
        0,
        0,
    ) == 0.0


def test_google_score_maximum():
    assert calculate_google_score(
        100,
        100,
    ) == 100.0


def test_growth_to_score():
    assert growth_to_score(0) == 50.0


def test_growth_to_score_positive():
    assert growth_to_score(100) == 100.0


def test_growth_to_score_negative():
    assert growth_to_score(-100) == 0.0


def test_growth_to_score_half_growth():
    assert growth_to_score(50) == 75.0


# ============================================================
# CONFIDENCE TESTS
# ============================================================


def test_confidence_score():
    score = calculate_confidence_score(
        evidence_count=5,
        platform_count=3,
        data_completeness=1.0,
    )

    assert score == 100.0


def test_confidence_score_no_evidence():
    score = calculate_confidence_score(
        evidence_count=0,
        platform_count=0,
        data_completeness=0.0,
    )

    assert score == 0.0


def test_confidence_score_partial():
    score = calculate_confidence_score(
        evidence_count=1,
        platform_count=1,
        data_completeness=1.0,
    )

    assert score == 48.0


# ============================================================
# CROSS PLATFORM TESTS
# ============================================================


def test_cross_platform_score():
    score = calculate_cross_platform_score(
        {
            "youtube": 100,
            "forum": 50,
            "google": 75,
        }
    )

    assert score == 77.5


def test_cross_platform_missing_platform():

    score = calculate_cross_platform_score(
        {
            "youtube": 100,
            "google": 50,
        }
    )

    assert score == 78.57


def test_cross_platform_youtube_only():
    assert calculate_cross_platform_score(
        {
            "youtube": 71,
        }
    ) == 71.0


def test_cross_platform_forum_only():
    assert calculate_cross_platform_score(
        {
            "forum": 71,
        }
    ) == 71.0


def test_cross_platform_google_only():
    assert calculate_cross_platform_score(
        {
            "google": 71,
        }
    ) == 71.0


def test_cross_platform_empty():
    assert calculate_cross_platform_score({}) == 0.0


def test_cross_platform_unknown_platform():
    assert calculate_cross_platform_score(
        {
            "unknown": 100,
        }
    ) == 0.0