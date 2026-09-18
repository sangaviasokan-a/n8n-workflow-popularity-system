from __future__ import annotations

import html
import re
import unicodedata
from typing import Any

COMMON_WORDS = {
    "tutorial",
    "tutorials",
    "how",
    "to",
    "guide",
    "guides",
    "step",
    "steps",
    "using",
    "use",
    "with",
    "the",
    "a",
    "an",
    "automation",
    "automations",
    "workflow",
    "workflows",
    "complete",
    "full",
    "course",
    "courses",
    "learn",
    "learning",
    "setup",
    "set",
    "up",
    "easy",
    "best",
    "simple",
    "beginner",
    "beginners",
    "advanced",
    "free",
    "new",
}

SUPPORTED_PLATFORMS = {
    "youtube",
    "forum",
    "google",
}


SUPPORTED_COUNTRIES = {
    "US",
    "IN",
}


def normalize_text(value: str) -> str:
    """
    Normalize arbitrary text for matching and deduplication.
    """

    if not isinstance(value, str):
        return ""

    value = html.unescape(value)

    value = unicodedata.normalize(
        "NFKC",
        value,
    )

    value = value.lower().strip()

    value = re.sub(
        r"[^a-z0-9\s]",
        " ",
        value,
    )

    value = re.sub(
        r"\s+",
        " ",
        value,
    )

    return value.strip()


def normalize_title(value: str) -> str:
    """
    Normalize workflow titles.
    """

    value = normalize_text(value)

    words = value.split()

    words = [
        word
        for word in words
        if word not in COMMON_WORDS
    ]

    return " ".join(words)


def normalize_record(
    record: dict[str, Any],
) -> dict[str, Any]:
    """
    Normalize a collector record while preserving
    the original fields.
    """

    result = dict(record)

    title = result.get("title", "")

    if title is None:
        title = ""

    normalized = normalize_title(
        str(title)
    )

    result["normalized_title"] = normalized

    return result


def normalize_workflow_title(
    title: str,
) -> str:
    """
    Backward-compatible workflow-title normalization.
    """

    return normalize_title(title)


def normalize_workflow_record(
    record: dict[str, Any],
) -> dict[str, Any]:
    result = normalize_record(record)

    platform = result.get("platform")

    if isinstance(platform, str):
        result["platform"] = platform.strip().lower()

    country = result.get("country")

    if isinstance(country, str):
        country = country.strip().upper()

        if country in SUPPORTED_COUNTRIES:
            result["country"] = country
        else:
            result["country"] = None

    return result