from app.processors.scorer import (
    calculate_cross_platform_score,
    calculate_engagement_score,
    calculate_youtube_score,
    calculate_forum_score,
    calculate_google_score,
    calculate_confidence_score,
    growth_to_score,
    log_normalize,
    normalize_batch,
)


def test_log_normalize_relative_to_maximum():
    low = log_normalize(100, 10000)
    high = log_normalize(10000, 10000)

    assert low < high
    assert high == 100.0


def test_normalize_batch():
    scores = normalize_batch([100, 1000, 10000])

    assert len(scores) == 3
    assert scores[0] < scores[1] < scores[2]
    assert scores[2] == 100.0


def test_normalize_batch_empty():
    assert normalize_batch([]) == []


def test_normalize_batch_zero_values():
    assert normalize_batch([0, 0, 0]) == [0.0, 0.0, 0.0]


def test_youtube_score():
    score = calculate_youtube_score(
        100,
        80,
        60,
        40,
    )

    assert score == 83.0


def test_forum_score():
    score = calculate_forum_score(
        100,
        80,
        60,
        40,
    )

    assert score == 77.0


def test_google_score():
    score = calculate_google_score(
        100,
        50,
    )

    assert score == 80.0


def test_cross_platform_score():
    score = calculate_cross_platform_score(
        {
            "youtube": 100,
            "forum": 80,
            "google": 60,
        }
    )

    assert score == 82.0


def test_cross_platform_missing_platform():
    score = calculate_cross_platform_score(
        {
            "youtube": 100,
        }
    )

    assert score == 100.0


def test_confidence_score():
    score = calculate_confidence_score(
        evidence_count=5,
        platform_count=3,
        data_completeness=1.0,
    )

    assert score == 100.0


def test_growth_to_score():
    assert growth_to_score(0) == 50.0
    assert growth_to_score(100) == 100.0
    assert growth_to_score(-100) == 0.0
