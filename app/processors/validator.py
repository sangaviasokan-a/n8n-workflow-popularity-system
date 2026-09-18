from __future__ import annotations

from datetime import datetime
from typing import Any
from urllib.parse import urlparse


SUPPORTED_PLATFORMS = {
    "youtube",
    "forum",
    "google",
}

SUPPORTED_COUNTRIES = {
    "US",
    "IN",
}


def _is_valid_url(value: Any) -> bool:
    if not isinstance(value, str):
        return False

    try:
        parsed = urlparse(value)

        return bool(
            parsed.scheme
            and parsed.netloc
        )

    except Exception:
        return False


def _is_non_negative_number(
    value: Any,
) -> bool:
    if value is None:
        return True

    try:
        return float(value) >= 0

    except (
        TypeError,
        ValueError,
    ):
        return False


def validate_record(
    record: dict[str, Any],
) -> bool:
    """
    Validate one collector record.

    Returns:
        True  -> valid
        False -> invalid
    """

    if not isinstance(record, dict):
        return False

    platform = str(
        record.get(
            "platform",
            "",
        )
    ).lower().strip()

    if platform not in SUPPORTED_PLATFORMS:
        return False

    source_id = record.get(
        "source_id"
    )

    if not source_id:
        return False

    title = record.get(
        "title"
    )

    if not title or not isinstance(
        title,
        str,
    ):
        return False

    url = record.get(
        "url"
    )

    if not _is_valid_url(url):
        return False

    # --------------------------------------------------------------
    # Country validation
    # --------------------------------------------------------------

    country = record.get(
        "country"
    )

    if country is not None:

        country = str(
            country
        ).upper().strip()

        if country not in SUPPORTED_COUNTRIES:
            return False

    # --------------------------------------------------------------
    # Numeric metrics
    # --------------------------------------------------------------

    numeric_fields = [
        "views",
        "likes",
        "comments",
        "replies",
        "contributors",
        "current_interest",
        "average_interest",
        "maximum_interest",
    ]

    for field in numeric_fields:

        if not _is_non_negative_number(
            record.get(field)
        ):
            return False

    # --------------------------------------------------------------
    # YouTube impossible metrics
    # --------------------------------------------------------------

    if platform == "youtube":

        views = float(
            record.get(
                "views",
                0,
            ) or 0
        )

        likes = float(
            record.get(
                "likes",
                0,
            ) or 0
        )

        comments = float(
            record.get(
                "comments",
                0,
            ) or 0
        )

        if likes > views:
            return False

        if comments > views:
            return False

    # --------------------------------------------------------------
    # Google Trends validation
    # --------------------------------------------------------------

    if platform == "google":

        for field in (
            "current_interest",
            "average_interest",
            "maximum_interest",
        ):

            value = record.get(
                field
            )

            if value is not None:

                try:
                    value = float(
                        value
                    )

                except (
                    TypeError,
                    ValueError,
                ):
                    return False

                if not 0 <= value <= 100:
                    return False

    # --------------------------------------------------------------
    # Datetime validation
    # --------------------------------------------------------------

    published_at = record.get(
        "published_at"
    )

    if published_at is not None:

        if isinstance(
            published_at,
            str,
        ):

            try:
                datetime.fromisoformat(
                    published_at.replace(
                        "Z",
                        "+00:00",
                    )
                )

            except ValueError:
                return False

    return True


def validate_workflow_record(
    record: dict[str, Any],
) -> tuple[bool, list[str]]:
    """
    Validate a workflow record and return
    detailed validation errors.

    Returns:
        (True, []) when valid.

        (False, [error_codes...]) when invalid.
    """

    errors: list[str] = []

    # --------------------------------------------------------------
    # Basic record validation
    # --------------------------------------------------------------

    if not isinstance(record, dict):
        return False, ["invalid_record"]

    platform = str(
        record.get(
            "platform",
            "",
        )
    ).lower().strip()

    if platform not in SUPPORTED_PLATFORMS:
        errors.append("unsupported_platform")

    # --------------------------------------------------------------
    # Source ID
    # --------------------------------------------------------------

    source_id = record.get(
        "source_id"
    )

    # Some existing collectors use video_id/topic_id/keyword.
    if not source_id:
        if platform == "youtube":
            source_id = record.get("video_id")

        elif platform == "forum":
            source_id = record.get("topic_id")

        elif platform == "google":
            source_id = record.get("keyword")

    if not source_id:
        errors.append("missing_source_id")

    # --------------------------------------------------------------
    # Title
    # --------------------------------------------------------------

    title = record.get(
        "title"
    )

    if not title or not isinstance(
        title,
        str,
    ) or not title.strip():
        errors.append("missing_title")

    # --------------------------------------------------------------
    # URL
    # --------------------------------------------------------------

    url = record.get(
        "url"
    )

    if not _is_valid_url(url):
        errors.append("invalid_url")

    # --------------------------------------------------------------
    # Country
    # --------------------------------------------------------------

    country = record.get(
        "country"
    )

    if country is not None:

        country_normalized = str(
            country
        ).upper().strip()

        if country_normalized not in SUPPORTED_COUNTRIES:
            errors.append("unsupported_country")

    # --------------------------------------------------------------
    # Numeric metrics
    # --------------------------------------------------------------

    numeric_fields = [
        "views",
        "likes",
        "comments",
        "replies",
        "contributors",
        "current_interest",
        "average_interest",
        "maximum_interest",
    ]

    for field in numeric_fields:

        value = record.get(
            field
        )

        if value is None:
            continue

        try:
            numeric_value = float(value)

        except (
            TypeError,
            ValueError,
        ):
            errors.append(
                f"invalid_{field}"
            )
            continue

        if numeric_value < 0:
            errors.append(
                f"negative_{field}"
            )

    # --------------------------------------------------------------
    # YouTube impossible metrics
    # --------------------------------------------------------------

    if platform == "youtube":

        try:
            views = float(
                record.get(
                    "views",
                    0,
                ) or 0
            )

            likes = float(
                record.get(
                    "likes",
                    0,
                ) or 0
            )

            comments = float(
                record.get(
                    "comments",
                    0,
                ) or 0
            )

            if likes > views:
                errors.append(
                    "likes_exceed_views"
                )

            if comments > views:
                errors.append(
                    "comments_exceed_views"
                )

        except (
            TypeError,
            ValueError,
        ):
            pass

    # --------------------------------------------------------------
    # Google Trends validation
    # --------------------------------------------------------------

    if platform == "google":

        for field in (
            "current_interest",
            "average_interest",
            "maximum_interest",
        ):

            value = record.get(
                field
            )

            if value is None:
                continue

            try:
                value = float(value)

            except (
                TypeError,
                ValueError,
            ):
                continue

            if not 0 <= value <= 100:
                errors.append(
                    f"invalid_{field}_range"
                )

    # --------------------------------------------------------------
    # Datetime validation
    # --------------------------------------------------------------

    published_at = record.get(
        "published_at"
    )

    if published_at is not None:

        if isinstance(
            published_at,
            str,
        ):

            try:
                datetime.fromisoformat(
                    published_at.replace(
                        "Z",
                        "+00:00",
                    )
                )

            except ValueError:
                errors.append(
                    "invalid_published_at"
                )

        elif not isinstance(
            published_at,
            datetime,
        ):
            errors.append(
                "invalid_published_at"
            )

    return (
        len(errors) == 0,
        errors,
    )