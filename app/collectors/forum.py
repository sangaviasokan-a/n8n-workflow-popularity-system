from __future__ import annotations

import logging
from datetime import datetime
from typing import Any

import httpx
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from app.collectors.base import BaseCollector

logger = logging.getLogger(__name__)

# n8n Community is powered by Discourse.
FORUM_API_BASE = "https://community.n8n.io"


class ForumCollector(BaseCollector):
    platform = "forum"

    def __init__(
        self,
        base_url: str = FORUM_API_BASE,
        timeout: float = 30.0,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    @retry(
        retry=retry_if_exception_type(
            (
                httpx.TimeoutException,
                httpx.NetworkError,
            )
        ),
        wait=wait_exponential(
            multiplier=1,
            min=1,
            max=8,
        ),
        stop=stop_after_attempt(3),
        reraise=True,
    )
    async def _request(
        self,
        endpoint: str,
        params: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """
        Perform a GET request against the n8n Community API.
        """

        url = f"{self.base_url}{endpoint}"

        async with httpx.AsyncClient(
            timeout=self.timeout
        ) as client:

            response = await client.get(
                url,
                params=params,
                headers={
                    "Accept": "application/json",
                    "User-Agent": "n8n-popularity-system/1.0",
                },
            )

            response.raise_for_status()

            return response.json()

    async def _get(
        self,
        endpoint: str,
        params: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """
        Compatibility wrapper around _request().
        """

        return await self._request(
            endpoint,
            params=params,
        )

    async def search_topics(
        self,
        query: str,
        page: int = 1,
    ) -> dict[str, Any]:
        """
        Search the n8n Community using Discourse's
        public search API.
        """

        if not query or not query.strip():
            return {}

        return await self._get(
            "/search.json",
            params={
                "q": query.strip(),
                "page": page,
            },
        )

    async def get_topic(
        self,
        topic_id: int | str,
    ) -> dict[str, Any]:
        """
        Fetch detailed information for a specific topic.
        """

        if not topic_id:
            return {}

        return await self._get(
            f"/t/{topic_id}.json"
        )

    @staticmethod
    def _parse_datetime(
        value: Any,
    ) -> datetime | None:
        """
        Safely parse an ISO datetime value.
        """

        if not value:
            return None

        if isinstance(value, datetime):
            return value

        if not isinstance(value, str):
            return None

        try:
            return datetime.fromisoformat(
                value.replace(
                    "Z",
                    "+00:00",
                )
            )
        except ValueError:
            return None

    @staticmethod
    def validate_metrics(
        views: int | float | None,
        replies: int | float | None,
        likes: int | float | None,
        contributors: int | float | None,
    ) -> bool:
        """
        Validate forum metrics.

        Metrics must:
        - be numeric when provided
        - be non-negative

        None is accepted because some Discourse responses
        may not contain every metric.
        """

        values = (
            views,
            replies,
            likes,
            contributors,
        )

        for value in values:

            if value is None:
                continue

            try:
                if float(value) < 0:
                    return False

            except (
                TypeError,
                ValueError,
            ):
                return False

        return True

    @staticmethod
    def _safe_int(
        value: Any,
    ) -> int:
        """
        Convert a value to a non-negative integer.
        """

        try:
            if value is None:
                return 0

            number = int(value)

            return max(
                number,
                0,
            )

        except (
            TypeError,
            ValueError,
        ):
            return 0

    def _normalize_topic(
        self,
        item: dict[str, Any],
    ) -> dict[str, Any] | None:
        """
        Convert a Discourse topic/search response into
        the repository's normalized forum record format.
        """

        if not isinstance(item, dict):
            return None

        topic_id = (
            item.get("id")
            or item.get("topic_id")
        )

        title = item.get("title")

        if not topic_id or not title:
            return None

        topic_id = str(topic_id).strip()

        title = str(title).strip()

        if not topic_id or not title:
            return None

        slug = item.get("slug")

        if slug:
            url = (
                f"{self.base_url}"
                f"/t/{slug}/{topic_id}"
            )
        else:
            url = (
                f"{self.base_url}"
                f"/t/{topic_id}"
            )

        created_at = (
            item.get("created_at")
            or item.get("created")
        )

        views = self._safe_int(
            item.get("views")
        )

        replies = self._safe_int(
            item.get("reply_count")
            or item.get("replies")
        )

        likes = self._safe_int(
            item.get("like_count")
            or item.get("likes")
        )

        contributors = self._safe_int(
            item.get("participant_count")
            or item.get("contributors")
        )

        # Validate before returning the record.
        if not self.validate_metrics(
            views,
            replies,
            likes,
            contributors,
        ):
            return None

        return {
            "platform": "forum",
            "source_id": topic_id,
            "topic_id": topic_id,
            "title": title,
            "description": (
                item.get("blurb")
                or item.get("excerpt")
                or ""
            ),
            "url": url,
            "published_at": self._parse_datetime(
                created_at
            ),
            "views": views,
            "replies": replies,
            "likes": likes,
            "contributors": contributors,

            # Never fabricate country information.
            "country": None,
        }

    async def collect(
        self,
        queries: list[str] | None = None,
        max_pages_per_query: int = 2,
        query: str | None = None,
    ) -> list[dict[str, Any]]:
        """
        Collect n8n Community topics for multiple queries.

        Topics are deduplicated by topic ID.

        If one query fails, collection continues with
        the remaining queries.
        """

        # Compatibility with a single-query call.
        if query is not None:
            queries = [query]

        if queries is None:
            queries = []

        records: list[dict[str, Any]] = []

        seen_topic_ids: set[str] = set()

        for raw_query in queries:

            if not raw_query:
                continue

            current_query = raw_query.strip()

            if not current_query:
                continue

            for page in range(
                1,
                max_pages_per_query + 1,
            ):

                try:
                    response = await self.search_topics(
                        query=current_query,
                        page=page,
                    )

                    topics = response.get(
                        "topics",
                        [],
                    )

                    # Stop pagination when no results
                    # are returned.
                    if not topics:
                        break

                    for topic in topics:

                        record = self._normalize_topic(
                            topic
                        )

                        if record is None:
                            continue

                        topic_id = str(
                            record["source_id"]
                        )

                        if topic_id in seen_topic_ids:
                            continue

                        seen_topic_ids.add(
                            topic_id
                        )

                        records.append(
                            record
                        )

                except Exception:
                    logger.exception(
                        "n8n Community search failed",
                        extra={
                            "query": current_query,
                            "page": page,
                        },
                    )

                    # Continue with the next query.
                    break

        logger.info(
            "Forum collection completed",
            extra={
                "queries": len(queries),
                "records": len(records),
            },
        )

        return records