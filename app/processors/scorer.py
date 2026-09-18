from __future__ import annotations

import math
from typing import Iterable


def min_max_normalize(
    value: float,
    minimum: float,
    maximum: float,
) -> float:
    """
    Normalize a value to a 0-100 range.
    """

    if maximum <= minimum:
        return 50.0

    value = max(
        minimum,
        min(value, maximum),
    )

    return (
        (value - minimum)
        / (maximum - minimum)
    ) * 100.0


def log_normalize(
    value: float,
    maximum: float,
) -> float:
    """
    Log-normalize a popularity metric against a batch maximum.

    Useful for heavily skewed metrics such as:

        - YouTube views
        - YouTube likes
        - Forum views
        - Forum replies
    """

    if value <= 0 or maximum <= 0:
        return 0.0

    value_log = math.log1p(value)

    maximum_log = math.log1p(
        maximum
    )

    return min(
        100.0,
        (
            value_log
            / maximum_log
        ) * 100.0,
    )


def normalize_batch(
    values: Iterable[float | None],
) -> list[float]:
    """
    Log-normalize a collection of popularity values.

    None represents unavailable data.

    None is treated as zero contribution during mathematical
    scoring, but the original database value remains NULL.

    This preserves the distinction between:

        NULL -> unavailable
        0    -> actual zero
    """

    values = list(values)

    numeric_values = [
        max(
            0.0,
            float(value),
        )
        for value in values
        if value is not None
    ]

    if not numeric_values:
        return [
            0.0
            for _ in values
        ]

    maximum = max(
        numeric_values
    )

    if maximum <= 0:
        return [
            0.0
            for _ in values
        ]

    return [
        (
            log_normalize(
                float(value),
                maximum,
            )
            if value is not None
            else 0.0
        )
        for value in values
    ]


def calculate_engagement_score(
    likes_per_view: float,
    comments_per_view: float,
) -> float:
    """
    Convert engagement ratios into a 0-100 score.

    Values are capped so extreme outliers don't dominate.
    """

    likes_per_view = max(
        0.0,
        float(likes_per_view),
    )

    comments_per_view = max(
        0.0,
        float(comments_per_view),
    )

    like_component = min(
        likes_per_view / 0.10,
        1.0,
    ) * 100.0

    comment_component = min(
        comments_per_view / 0.02,
        1.0,
    ) * 100.0

    return round(
        like_component * 0.6
        + comment_component * 0.4,
        2,
    )


def calculate_youtube_score(
    views_score: float,
    likes_score: float,
    comments_score: float,
    engagement_score: float,
) -> float:
    """
    YouTube popularity score.

    Assignment-defined weighting:

        Views       = 50%
        Likes       = 25%
        Comments    = 15%
        Engagement  = 10%
    """

    score = (
        views_score * 0.50
        + likes_score * 0.25
        + comments_score * 0.15
        + engagement_score * 0.10
    )

    return round(
        min(
            max(score, 0.0),
            100.0,
        ),
        2,
    )


def calculate_forum_score(
    views_score: float,
    replies_score: float,
    likes_score: float,
    contributors_score: float,
) -> float:
    """
    Forum popularity score.

    Assignment-defined weighting:

        Views        = 35%
        Replies      = 30%
        Likes        = 20%
        Contributors = 15%
    """

    score = (
        views_score * 0.35
        + replies_score * 0.30
        + likes_score * 0.20
        + contributors_score * 0.15
    )

    return round(
        min(
            max(score, 0.0),
            100.0,
        ),
        2,
    )


def calculate_google_score(
    search_interest_score: float,
    trend_growth_score: float,
) -> float:
    """
    Google Trends popularity score.

    Assignment-defined weighting:

        Search interest = 60%
        Trend growth   = 40%
    """

    score = (
        search_interest_score * 0.60
        + trend_growth_score * 0.40
    )

    return round(
        min(
            max(score, 0.0),
            100.0,
        ),
        2,
    )


def calculate_confidence_score(
    evidence_count: int,
    platform_count: int,
    data_completeness: float,
) -> float:
    """
    Calculate confidence separately from popularity.

    Popularity:
        How popular does this appear?

    Confidence:
        How strong is the evidence?
    """

    evidence_component = min(
        max(evidence_count, 0) / 5,
        1.0,
    ) * 100.0

    platform_component = min(
        max(platform_count, 0) / 3,
        1.0,
    ) * 100.0

    completeness_component = (
        max(
            0.0,
            min(
                data_completeness,
                1.0,
            ),
        )
        * 100.0
    )

    score = (
        evidence_component * 0.40
        + platform_component * 0.30
        + completeness_component * 0.30
    )

    return round(
        min(
            max(score, 0.0),
            100.0,
        ),
        2,
    )


def calculate_cross_platform_score(
    platform_scores: dict[str, float],
) -> float:
    """
    Combine available platform scores.

    Default:

        YouTube = 40%
        Forum   = 30%
        Google  = 30%

    Missing platforms are excluded and remaining weights
    are renormalized.
    """

    weights = {
        "youtube": 0.40,
        "forum": 0.30,
        "google": 0.30,
    }

    available = {
        platform: float(score)
        for platform, score in platform_scores.items()
        if (
            platform in weights
            and score is not None
        )
    }

    if not available:
        return 0.0

    total_weight = sum(
        weights[platform]
        for platform in available
    )

    if total_weight <= 0:
        return 0.0

    score = sum(
        available[platform]
        * weights[platform]
        for platform in available
    ) / total_weight

    return round(
        min(
            max(score, 0.0),
            100.0,
        ),
        2,
    )


def growth_to_score(
    growth_percentage: float,
) -> float:
    """
    Convert trend growth percentage into a bounded 0-100 score.

    100% growth or higher -> 100
    0% growth             -> 50
    Negative growth       -> lower score
    """

    growth_percentage = float(
        growth_percentage
    )

    score = 50.0 + (
        growth_percentage / 2.0
    )

    return round(
        min(
            max(score, 0.0),
            100.0,
        ),
        2,
    )