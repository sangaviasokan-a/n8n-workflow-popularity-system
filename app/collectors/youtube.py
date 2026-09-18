from __future__ import annotations

import logging
from html import unescape
from typing import Any

import httpx
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from app.config import settings


logger = logging.getLogger(__name__)


YOUTUBE_API_BASE = (
    "https://www.googleapis.com/youtube/v3"
)


class SearchVideoResults(list):
    """
    Hybrid result object.

    Behaves like:
        list[dict]

    while also supporting:
        result["items"]
        result.get("items")

    This keeps compatibility with older tests/callers that
    expect the raw YouTube API response format.
    """

    def __init__(
        self,
        records: list[dict[str, Any]],
        raw_items: list[dict[str, Any]],
    ) -> None:
        super().__init__(records)
        self._raw_items = raw_items

    def __getitem__(
        self,
        key: int | slice | str,
    ):
        if key == "items":
            return self._raw_items

        return super().__getitem__(key)

    def get(
        self,
        key: str,
        default: Any = None,
    ) -> Any:
        if key == "items":
            return self._raw_items

        return default


class YouTubeCollector:

    platform = "youtube"

    # ========================================================
    # INITIALIZATION
    # ========================================================

    def __init__(
        self,
        api_key: str | None = None,
        timeout: float = 30.0,
    ) -> None:

        self.api_key = (
            api_key
            or settings.youtube_api_key
        )

        self.timeout = timeout

        if not self.api_key:
            raise ValueError(
                "YOUTUBE_API_KEY is not configured."
            )

    # ========================================================
    # HTTP REQUEST
    # ========================================================

    @retry(
        retry=retry_if_exception_type(
            (
                httpx.TimeoutException,
                httpx.NetworkError,
                httpx.HTTPStatusError,
            )
        ),
        wait=wait_exponential(
            multiplier=1,
            min=1,
            max=10,
        ),
        stop=stop_after_attempt(3),
        reraise=True,
    )
    async def _request(
        self,
        endpoint: str,
        params: dict[str, Any],
    ) -> dict[str, Any]:

        url = (
            f"{YOUTUBE_API_BASE}/{endpoint}"
        )

        request_params = {
            **params,
            "key": self.api_key,
        }

        async with httpx.AsyncClient(
            timeout=self.timeout
        ) as client:

            response = await client.get(
                url,
                params=request_params,
            )

            # Retry temporary/rate-limit failures.
            if response.status_code in {
                429,
                500,
                502,
                503,
                504,
            }:
                response.raise_for_status()

            # Raise all HTTP errors.
            response.raise_for_status()

            return response.json()

    async def _get(
        self,
        endpoint: str,
        params: dict[str, Any],
    ) -> dict[str, Any]:
        """
        Compatibility wrapper.

        Tests can mock _get() without touching the HTTP layer.
        """

        return await self._request(
            endpoint,
            params,
        )

    # ========================================================
    # VALIDATE STATISTICS
    # ========================================================

    @staticmethod
    def validate_statistics(
        views: int | float | None,
        likes: int | float | None,
        comments: int | float | None,
    ) -> bool:
        """
        Validate YouTube statistics.

        Rules:
        - views cannot be negative
        - likes cannot be negative
        - comments cannot be negative
        - likes cannot exceed views
        - comments cannot exceed views
        """

        try:

            views_value = float(
                views or 0
            )

            likes_value = float(
                likes or 0
            )

            comments_value = float(
                comments or 0
            )

        except (
            TypeError,
            ValueError,
        ):

            return False

        if views_value < 0:
            return False

        if likes_value < 0:
            return False

        if comments_value < 0:
            return False

        if likes_value > views_value:
            return False

        if comments_value > views_value:
            return False

        return True

    # ========================================================
    # CALCULATE RATIOS
    # ========================================================

    @staticmethod
    def calculate_ratios(
        views: int | float,
        likes: int | float,
        comments: int | float,
    ) -> dict[str, float]:
        """
        Calculate engagement ratios safely.
        """

        try:

            views_value = float(
                views or 0
            )

            likes_value = float(
                likes or 0
            )

            comments_value = float(
                comments or 0
            )

        except (
            TypeError,
            ValueError,
        ):

            return {
                "likes_per_view": 0.0,
                "comments_per_view": 0.0,
            }

        if views_value <= 0:

            return {
                "likes_per_view": 0.0,
                "comments_per_view": 0.0,
            }

        return {
            "likes_per_view": (
                likes_value / views_value
            ),
            "comments_per_view": (
                comments_value / views_value
            ),
        }

    # ========================================================
    # SEARCH VIDEOS
    # ========================================================

    async def search_videos(
        self,
        query: str | None = None,
        max_results: int = 25,
        page_token: str | None = None,
        keyword: str | None = None,
    ) -> SearchVideoResults:

        # ----------------------------------------------------
        # keyword= compatibility
        # ----------------------------------------------------

        if keyword is not None:
            query = keyword

        # ----------------------------------------------------
        # Empty query
        # ----------------------------------------------------

        if not query or not query.strip():

            return SearchVideoResults(
                records=[],
                raw_items=[],
            )

        query = query.strip()

        # ----------------------------------------------------
        # YouTube maximum = 50
        # ----------------------------------------------------

        max_results = max(
            1,
            min(
                max_results,
                50,
            ),
        )

        params: dict[str, Any] = {
            "part": "snippet",
            "q": query,
            "type": "video",
            "maxResults": max_results,
            "order": "relevance",
        }

        if page_token:
            params["pageToken"] = page_token

        logger.info(
            "youtube_search_started",
            extra={
                "query": query,
                "max_results": max_results,
            },
        )

        # ----------------------------------------------------
        # API REQUEST
        # ----------------------------------------------------

        data = await self._get(
            "search",
            params,
        )

        raw_items = (
            data.get(
                "items",
                [],
            )
            if isinstance(
                data,
                dict,
            )
            else []
        )

        if not isinstance(
            raw_items,
            list,
        ):
            raw_items = []

        # ----------------------------------------------------
        # NORMALIZE
        # ----------------------------------------------------

        records: list[
            dict[str, Any]
        ] = []

        for item in raw_items:

            if not isinstance(
                item,
                dict,
            ):
                continue

            record = (
                self._normalize_video(
                    item
                )
            )

            if record is None:
                continue

            record["keyword"] = query

            records.append(record)

        logger.info(
            "youtube_search_completed",
            extra={
                "query": query,
                "result_count": len(records),
            },
        )

        return SearchVideoResults(
            records=records,
            raw_items=raw_items,
        )

    # ========================================================
    # GET VIDEO DETAILS
    # ========================================================

    async def get_video_details(
        self,
        video_ids: list[str],
    ) -> dict[str, Any]:
        """
        Retrieve full YouTube video details.

        YouTube supports a maximum of 50 IDs per request.
        """

        if not video_ids:

            return {
                "items": []
            }

        clean_ids = [
            str(video_id).strip()
            for video_id in video_ids
            if video_id
        ]

        clean_ids = list(
            dict.fromkeys(clean_ids)
        )

        clean_ids = clean_ids[:50]

        return await self._get(
            "videos",
            {
                "part": (
                    "snippet,"
                    "statistics,"
                    "contentDetails"
                ),
                "id": ",".join(clean_ids),
            },
        )

    # ========================================================
    # GET VIDEO STATISTICS
    # ========================================================

    async def get_video_statistics(
        self,
        video_ids: list[str],
    ) -> dict[
        str,
        dict[str, int],
    ]:

        if not video_ids:
            return {}

        clean_ids = [
            str(video_id).strip()
            for video_id in video_ids
            if video_id
        ]

        clean_ids = list(
            dict.fromkeys(clean_ids)
        )

        results: dict[
            str,
            dict[str, int],
        ] = {}

        # YouTube maximum = 50 IDs/request.
        for start in range(
            0,
            len(clean_ids),
            50,
        ):

            batch = clean_ids[
                start:start + 50
            ]

            try:

                response = await self._get(
                    "videos",
                    {
                        "part": "statistics",
                        "id": ",".join(batch),
                    },
                )

                items = (
                    response.get(
                        "items",
                        [],
                    )
                    if isinstance(
                        response,
                        dict,
                    )
                    else []
                )

                if not isinstance(
                    items,
                    list,
                ):
                    items = []

                for item in items:

                    if not isinstance(
                        item,
                        dict,
                    ):
                        continue

                    video_id = str(
                        item.get("id")
                        or ""
                    ).strip()

                    if not video_id:
                        continue

                    statistics = (
                        item.get(
                            "statistics"
                        )
                        or {}
                    )

                    if not isinstance(
                        statistics,
                        dict,
                    ):
                        continue

                    try:

                        views = int(
                            statistics.get(
                                "viewCount",
                                0,
                            )
                            or 0
                        )

                        likes = int(
                            statistics.get(
                                "likeCount",
                                0,
                            )
                            or 0
                        )

                        comments = int(
                            statistics.get(
                                "commentCount",
                                0,
                            )
                            or 0
                        )

                    except (
                        TypeError,
                        ValueError,
                    ):

                        logger.warning(
                            "Invalid YouTube statistics",
                            extra={
                                "video_id": video_id,
                            },
                        )

                        continue

                    if not self.validate_statistics(
                        views,
                        likes,
                        comments,
                    ):

                        logger.warning(
                            "YouTube statistics validation failed",
                            extra={
                                "video_id": video_id,
                                "views": views,
                                "likes": likes,
                                "comments": comments,
                            },
                        )

                        continue

                    results[
                        video_id
                    ] = {
                        "views": views,
                        "likes": likes,
                        "comments": comments,
                    }

            except Exception:

                logger.exception(
                    "YouTube statistics request failed",
                    extra={
                        "video_count": len(batch),
                    },
                )

                # Gracefully continue.
                continue

        return results

    # ========================================================
    # NORMALIZE VIDEO
    # ========================================================

    @staticmethod
    def _normalize_video(
        item: dict[str, Any],
    ) -> dict[str, Any] | None:
        """
        Convert YouTube API response data into
        the normalized application record.
        """

        if not isinstance(
            item,
            dict,
        ):
            return None

        # ----------------------------------------------------
        # VIDEO ID
        # ----------------------------------------------------

        video_id = (
            item.get("id")
            or ""
        )

        if isinstance(
            video_id,
            dict,
        ):

            video_id = (
                video_id.get(
                    "videoId"
                )
                or ""
            )

        video_id = str(
            video_id
        ).strip()

        if not video_id:
            return None

        # ----------------------------------------------------
        # SNIPPET
        # ----------------------------------------------------

        snippet = (
            item.get(
                "snippet"
            )
            or {}
        )

        if not isinstance(
            snippet,
            dict,
        ):
            snippet = {}

        # ----------------------------------------------------
        # STATISTICS
        # ----------------------------------------------------

        statistics = (
            item.get(
                "statistics"
            )
            or {}
        )

        if not isinstance(
            statistics,
            dict,
        ):
            statistics = {}

        # ----------------------------------------------------
        # TITLE
        # ----------------------------------------------------

        title = str(
            snippet.get(
                "title"
            )
            or ""
        ).strip()

        if not title:
            return None

        title = unescape(title)

        # ----------------------------------------------------
        # DESCRIPTION
        # ----------------------------------------------------

        description = unescape(
            str(
                snippet.get(
                    "description"
                )
                or ""
            )
        )

        # ----------------------------------------------------
        # METRICS
        # ----------------------------------------------------

        try:

            views = int(
                statistics.get(
                    "viewCount",
                    0,
                )
                or 0
            )

            likes = int(
                statistics.get(
                    "likeCount",
                    0,
                )
                or 0
            )

            comments = int(
                statistics.get(
                    "commentCount",
                    0,
                )
                or 0
            )

        except (
            TypeError,
            ValueError,
        ):

            return None

        if not YouTubeCollector.validate_statistics(
            views,
            likes,
            comments,
        ):
            return None

        # ----------------------------------------------------
        # RATIOS
        # ----------------------------------------------------

        ratios = (
            YouTubeCollector.calculate_ratios(
                views,
                likes,
                comments,
            )
        )

        # ----------------------------------------------------
        # PUBLISHED DATE
        # ----------------------------------------------------

        published_at = (
            snippet.get(
                "publishedAt"
            )
        )

        # ----------------------------------------------------
        # CHANNEL
        # ----------------------------------------------------

        channel_id = (
            snippet.get(
                "channelId"
            )
        )

        channel_title = (
            snippet.get(
                "channelTitle"
            )
        )

        # ----------------------------------------------------
        # THUMBNAIL
        # ----------------------------------------------------

        thumbnail_url = None

        thumbnails = (
            snippet.get(
                "thumbnails"
            )
            or {}
        )

        if isinstance(
            thumbnails,
            dict,
        ):

            for quality in (
                "high",
                "medium",
                "default",
            ):

                thumbnail = (
                    thumbnails.get(
                        quality
                    )
                )

                if not isinstance(
                    thumbnail,
                    dict,
                ):
                    continue

                candidate = (
                    thumbnail.get(
                        "url"
                    )
                )

                if candidate:

                    thumbnail_url = str(
                        candidate
                    )

                    break

        # ----------------------------------------------------
        # NORMALIZED RECORD
        # ----------------------------------------------------

        return {
            "platform": "youtube",

            "source_id": video_id,

            "video_id": video_id,

            "title": title,

            "description": description,

            "url": (
                "https://www.youtube.com/"
                f"watch?v={video_id}"
            ),

            "published_at": published_at,

            "channel_id": channel_id,

            "channel_title": channel_title,

            "thumbnail_url": thumbnail_url,

            "views": views,

            "likes": likes,

            "comments": comments,

            "likes_per_view": (
                ratios[
                    "likes_per_view"
                ]
            ),

            "comments_per_view": (
                ratios[
                    "comments_per_view"
                ]
            ),

            # YouTube API does not provide
            # audience-country information
            # for this collector.
            "country": None,
        }

    # ========================================================
    # COLLECT
    # ========================================================

    async def collect(
        self,
        queries: list[str] | None = None,
        max_results_per_query: int = 25,
        keyword: str | None = None,
        max_results: int | None = None,
    ) -> list[dict[str, Any]]:
        """
        Collect workflow-related YouTube videos.

        Pipeline:

            Search
                ↓
            Deduplicate
                ↓
            Normalize
                ↓
            Statistics
                ↓
            Validate
                ↓
            Engagement ratios
                ↓
            Final records

        Supports:

            collect(
                queries=["n8n automation"]
            )

        and:

            collect(
                keyword="n8n Gmail automation",
                max_results=5
            )
        """

        # ----------------------------------------------------
        # COMPATIBILITY
        # ----------------------------------------------------

        if keyword is not None:
            queries = [keyword]

        if queries is None:
            queries = []

        if max_results is not None:
            max_results_per_query = max_results

        # ----------------------------------------------------
        # DISCOVERY STATE
        # ----------------------------------------------------

        video_ids: list[str] = []

        seen_ids: set[str] = set()

        video_keywords: dict[
            str,
            str,
        ] = {}

        # Search endpoint already gives us enough metadata
        # for normalized results.
        search_records: dict[
            str,
            dict[str, Any],
        ] = {}

        # ====================================================
        # STEP 1 — SEARCH
        # ====================================================

        for query in queries:

            if not query:
                continue

            query = query.strip()

            if not query:
                continue

            try:

                response = await self.search_videos(
                    query=query,
                    max_results=max_results_per_query,
                )

                # ------------------------------------------------
                # NORMALIZED SEARCH RESULTS
                # ------------------------------------------------

                if isinstance(
                    response,
                    list,
                ):

                    for record in response:

                        if not isinstance(
                            record,
                            dict,
                        ):
                            continue

                        video_id = str(
                            record.get(
                                "video_id"
                            )
                            or record.get(
                                "source_id"
                            )
                            or ""
                        ).strip()

                        if not video_id:
                            continue

                        if video_id not in seen_ids:

                            seen_ids.add(
                                video_id
                            )

                            video_ids.append(
                                video_id
                            )

                        keyword_value = str(
                            record.get(
                                "keyword"
                            )
                            or query
                        )

                        video_keywords[
                            video_id
                        ] = keyword_value

                        if (
                            video_id
                            not in search_records
                        ):

                            search_records[
                                video_id
                            ] = dict(record)

                # ------------------------------------------------
                # RAW/LEGACY RESPONSE
                # ------------------------------------------------

                else:

                    items = (
                        response.get(
                            "items",
                            [],
                        )
                        if isinstance(
                            response,
                            dict,
                        )
                        else []
                    )

                    if not isinstance(
                        items,
                        list,
                    ):
                        items = []

                    for item in items:

                        if not isinstance(
                            item,
                            dict,
                        ):
                            continue

                        item_id = item.get(
                            "id"
                        )

                        if isinstance(
                            item_id,
                            dict,
                        ):

                            video_id = (
                                item_id.get(
                                    "videoId"
                                )
                                or ""
                            )

                        else:

                            video_id = (
                                item_id
                                or ""
                            )

                        video_id = str(
                            video_id
                        ).strip()

                        if not video_id:
                            continue

                        if video_id not in seen_ids:

                            seen_ids.add(
                                video_id
                            )

                            video_ids.append(
                                video_id
                            )

                        video_keywords[
                            video_id
                        ] = query

            except Exception:

                logger.exception(
                    "YouTube search failed",
                    extra={
                        "query": query,
                    },
                )

                continue

        # ====================================================
        # NO RESULTS
        # ====================================================

        if not video_ids:

            logger.warning(
                "No YouTube videos discovered"
            )

            return []

        # ====================================================
        # STEP 2 — GET DETAILS ONLY WHEN NEEDED
        # ====================================================

        missing_detail_ids = [
            video_id
            for video_id in video_ids
            if video_id not in search_records
        ]

        detail_records: dict[
            str,
            dict[str, Any],
        ] = {}

        for start in range(
            0,
            len(missing_detail_ids),
            50,
        ):

            batch_ids = (
                missing_detail_ids[
                    start:start + 50
                ]
            )

            if not batch_ids:
                continue

            try:

                response = await self.get_video_details(
                    batch_ids
                )

                items = (
                    response.get(
                        "items",
                        [],
                    )
                    if isinstance(
                        response,
                        dict,
                    )
                    else []
                )

                if not isinstance(
                    items,
                    list,
                ):
                    items = []

                for item in items:

                    record = (
                        self._normalize_video(
                            item
                        )
                    )

                    if record is None:
                        continue

                    video_id = str(
                        record.get(
                            "video_id"
                        )
                            or ""
                    ).strip()

                    if not video_id:
                        continue

                    detail_records[
                        video_id
                    ] = record

            except Exception:

                logger.exception(
                    "YouTube video details request failed",
                    extra={
                        "video_count": len(
                            batch_ids
                        ),
                    },
                )

                continue

        # Add legacy detail records.
        for (
            video_id,
            record,
        ) in detail_records.items():

            if video_id not in search_records:

                search_records[
                    video_id
                ] = record

        # ====================================================
        # STEP 3 — GET STATISTICS
        # ====================================================

        try:

            statistics = (
                await self.get_video_statistics(
                    video_ids
                )
            )

        except Exception:

            logger.exception(
                "YouTube statistics collection failed"
            )

            statistics = {}

        # ====================================================
        # STEP 4 — MERGE + VALIDATE
        # ====================================================

        records: list[
            dict[str, Any]
        ] = []

        for video_id in video_ids:

            record = search_records.get(
                video_id
            )

            if record is None:
                continue

            # Do not mutate search_records.
            record = dict(record)

            # Guarantee canonical source identity even when a
            # legacy/mocked search result omits these fields.
            record["platform"] = self.platform
            record["video_id"] = video_id
            record["source_id"] = video_id

            stats = (
                statistics.get(
                    video_id
                )
                if isinstance(
                    statistics,
                    dict,
                )
                else None
            )

            # ------------------------------------------------
            # Real statistics available
            # ------------------------------------------------

            if stats is not None:

                try:

                    views = int(
                        stats.get(
                            "views",
                            0,
                        )
                        or 0
                    )

                    likes = int(
                        stats.get(
                            "likes",
                            0,
                        )
                        or 0
                    )

                    comments = int(
                        stats.get(
                            "comments",
                            0,
                        )
                        or 0
                    )

                except (
                    TypeError,
                    ValueError,
                ):

                    logger.warning(
                        "Invalid statistics during merge",
                        extra={
                            "video_id": video_id,
                        },
                    )

                    continue

                if not self.validate_statistics(
                    views,
                    likes,
                    comments,
                ):

                    logger.warning(
                        "Merged YouTube statistics failed validation",
                        extra={
                            "video_id": video_id,
                            "views": views,
                            "likes": likes,
                            "comments": comments,
                        },
                    )

                    continue

                ratios = (
                    self.calculate_ratios(
                        views,
                        likes,
                        comments,
                    )
                )

                record["views"] = views

                record["likes"] = likes

                record["comments"] = comments

                record["likes_per_view"] = (
                    ratios[
                        "likes_per_view"
                    ]
                )

                record["comments_per_view"] = (
                    ratios[
                        "comments_per_view"
                    ]
                )

            # ------------------------------------------------
            # No separate statistics returned.
            # Validate existing normalized metrics.
            # ------------------------------------------------

            else:

                views = record.get(
                    "views",
                    0,
                )

                likes = record.get(
                    "likes",
                    0,
                )

                comments = record.get(
                    "comments",
                    0,
                )

                if not self.validate_statistics(
                    views,
                    likes,
                    comments,
                ):
                    continue

            # ------------------------------------------------
            # Discovery keyword
            # ------------------------------------------------

            record["keyword"] = (
                video_keywords.get(
                    video_id
                )
            )

            # ------------------------------------------------
            # Country
            # ------------------------------------------------

            # We do NOT infer audience country.
            record["country"] = None

            records.append(
                record
            )

        # ====================================================
        # STEP 5 — FINAL DEDUPLICATION
        # ====================================================

        unique_records: dict[
            str,
            dict[str, Any],
        ] = {}

        for record in records:

            video_id = str(
                record.get(
                    "video_id"
                )
                or record.get(
                    "source_id"
                )
                or ""
            ).strip()

            if not video_id:
                continue

            if video_id not in unique_records:

                unique_records[
                    video_id
                ] = record

        records = list(
            unique_records.values()
        )

        # ====================================================
        # LOG
        # ====================================================

        logger.info(
            "YouTube collection completed",
            extra={
                "queries": len(queries),
                "discovered_video_ids": len(
                    video_ids
                ),
                "detail_records": len(
                    detail_records
                ),
                "final_records": len(
                    records
                ),
            },
        )

        return records