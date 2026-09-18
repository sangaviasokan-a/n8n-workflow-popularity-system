from __future__ import annotations

import asyncio
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
        max_concurrency: int = 5,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.max_concurrency = max_concurrency

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
    ) -> int | None:
        """
        Convert a value to a non-negative integer.

        None remains None so that an unavailable metric
        is not confused with a true zero.
        """

        if value is None:
            return None

        try:
            number = int(value)

            return max(
                number,
                0,
            )

        except (
            TypeError,
            ValueError,
        ):
            return None

    def _normalize_topic(
        self,
        item: dict[str, Any],
        detailed: dict[str, Any] | None = None,
    ) -> dict[str, Any] | None:
        """
        Convert a Discourse topic/search response into
        the repository's normalized forum record format.

        Detailed topic-level metrics are preferred because
        Discourse search results do not reliably contain
        views, likes, or participant counts.
        """

        if not isinstance(item, dict):
            return None

        if not isinstance(detailed, dict):
            detailed = {}

        topic_id = (
            detailed.get("id")
            or item.get("id")
            or item.get("topic_id")
        )

        title = (
            detailed.get("title")
            or item.get("title")
        )

        if not topic_id or not title:
            return None

        topic_id = str(topic_id).strip()
        title = str(title).strip()

        if not topic_id or not title:
            return None

        slug = (
            detailed.get("slug")
            or item.get("slug")
        )

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
            detailed.get("created_at")
            or item.get("created_at")
            or item.get("created")
        )

        # Discourse topic-level fields.
        #
        # Important:
        # "views" is the topic's actual view count.
        # "reads" belongs to an individual post and is
        # not used as the topic view metric.
        views = self._safe_int(
            detailed.get("views")
            if "views" in detailed
            else item.get("views")
        )

        replies = self._safe_int(
            detailed.get("reply_count")
            if "reply_count" in detailed
            else (
                item.get("reply_count")
                or item.get("replies")
            )
        )

        likes = self._safe_int(
            detailed.get("like_count")
            if "like_count" in detailed
            else (
                item.get("like_count")
                or item.get("likes")
            )
        )

        contributors = self._safe_int(
            detailed.get("participant_count")
            if "participant_count" in detailed
            else (
                item.get("participant_count")
                or item.get("contributors")
            )
        )

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
                detailed.get("blurb")
                or detailed.get("excerpt")
                or item.get("blurb")
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

    async def _fetch_detailed_topic(
        self,
        item: dict[str, Any],
        semaphore: asyncio.Semaphore,
    ) -> dict[str, Any] | None:
        """
        Fetch detailed topic information with bounded
        concurrency.
        """

        topic_id = (
            item.get("id")
            or item.get("topic_id")
        )

        if not topic_id:
            return None

        async with semaphore:

            try:
                detailed = await self.get_topic(
                    topic_id
                )

                return self._normalize_topic(
                    item,
                    detailed,
                )

            except Exception:
                logger.exception(
                    "n8n Community topic fetch failed",
                    extra={
                        "topic_id": topic_id,
                    },
                )

                # Preserve the topic if detailed metrics
                # cannot be fetched. Search data may still
                # contain useful fields.
                return self._normalize_topic(
                    item,
                    None,
                )

    async def collect(
        self,
        queries: list[str] | None = None,
        max_pages_per_query: int = 2,
        query: str | None = None,
    ) -> list[dict[str, Any]]:
        """
        Collect n8n Community topics for multiple queries.

        Topics are deduplicated by topic ID.

        Detailed topic metrics are fetched concurrently
        with a bounded concurrency limit.

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

        # First collect unique search-result topics.
        search_items: list[dict[str, Any]] = []

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

                    if not topics:
                        break

                    for topic in topics:

                        if not isinstance(
                            topic,
                            dict,
                        ):
                            continue

                        topic_id = (
                            topic.get("id")
                            or topic.get("topic_id")
                        )

                        if not topic_id:
                            continue

                        topic_id = str(
                            topic_id
                        ).strip()

                        if not topic_id:
                            continue

                        if topic_id in seen_topic_ids:
                            continue

                        seen_topic_ids.add(
                            topic_id
                        )

                        search_items.append(
                            topic
                        )

                except Exception:
                    logger.exception(
                        "n8n Community search failed",
                        extra={
                            "query": current_query,
                            "page": page,
                        },
                    )

                    break

        # Fetch detailed topic data with bounded
        # concurrency instead of making hundreds of
        # sequential requests.
        semaphore = asyncio.Semaphore(
            max(
                1,
                self.max_concurrency,
            )
        )

        detailed_records = await asyncio.gather(
            *[
                self._fetch_detailed_topic(
                    item,
                    semaphore,
                )
                for item in search_items
            ],
            return_exceptions=False,
        )

        for record in detailed_records:

            if record is None:
                continue

            records.append(record)

        logger.info(
            "Forum collection completed",
            extra={
                "queries": len(queries),
                "search_topics": len(search_items),
                "records": len(records),
            },
        )

        return records