from __future__ import annotations

import logging
from typing import Any

from pytrends.request import TrendReq

from app.collectors.base import BaseCollector

logger = logging.getLogger(__name__)


class GoogleTrendsCollector(BaseCollector):
    platform = "google"

    COUNTRY_CODES = {
        "US": "united_states",
        "IN": "india",
    }

    def __init__(
        self,
        timeout: tuple[int, int] = (10, 30),
    ) -> None:
        self.timeout = timeout

    def _create_client(self) -> TrendReq:
        return TrendReq(
            hl="en-US",
            tz=330,
            timeout=self.timeout,
            retries=2,
            backoff_factor=1,
        )

    @staticmethod
    def _calculate_growth(values: list[int]) -> float:
        """
        Calculate percentage growth between the first
        and last non-zero values.

        Example:
        [20, 25, 30] -> 50% growth
        """

        if len(values) < 2:
            return 0.0

        first = values[0]
        last = values[-1]

        if first <= 0:
            return 0.0

        return round(
            ((last - first) / first) * 100,
            2,
        )

    @staticmethod
    def _safe_int(value: Any) -> int:
        try:
            return int(value)
        except (TypeError, ValueError):
            return 0

    def collect_keyword(
        self,
        keyword: str,
        country: str,
        timeframe: str = "today 12-m",
    ) -> dict[str, Any] | None:

        keyword = keyword.strip()

        if not keyword:
            logger.warning(
                "google_trends_empty_keyword"
            )
            return None

        country = country.upper().strip()

        if country not in self.COUNTRY_CODES:
            logger.warning(
                "google_trends_invalid_country",
                extra={"country": country},
            )
            return None

        geo = "US" if country == "US" else "IN"

        logger.info(
            "google_trends_collection_started",
            extra={
                "keyword": keyword,
                "country": country,
                "timeframe": timeframe,
            },
        )

        try:
            client = self._create_client()

            client.build_payload(
                kw_list=[keyword],
                timeframe=timeframe,
                geo=geo,
            )

            dataframe = client.interest_over_time()

            if dataframe.empty:
                logger.info(
                    "google_trends_no_results",
                    extra={
                        "keyword": keyword,
                        "country": country,
                    },
                )
                return None

            values = [
                self._safe_int(value)
                for value in dataframe[keyword].tolist()
            ]

            values = [
                value
                for value in values
                if value >= 0
            ]

            if not values:
                return None

            current_interest = values[-1]

            average_interest = round(
                sum(values) / len(values),
                2,
            )

            maximum_interest = max(values)

            trend_growth = self._calculate_growth(
                values
            )

            record = {
                "platform": self.platform,
                "title": keyword,
                "normalized_title": keyword.lower(),
                "url": (
                    "https://trends.google.com/"
                    "trends/explore"
                    f"?q={keyword.replace(' ', '%20')}"
                    f"&geo={geo}"
                ),
                "source_id": (
                    f"google-trends:{country}:"
                    f"{keyword.lower()}"
                ),
                "country": country,
                "keyword": keyword,
                "timeframe": timeframe,
                "current_interest": current_interest,
                "average_interest": average_interest,
                "maximum_interest": maximum_interest,
                "trend_growth": trend_growth,
                "data_points": len(values),
            }

            logger.info(
                "google_trends_collection_completed",
                extra={
                    "keyword": keyword,
                    "country": country,
                    "current_interest": current_interest,
                    "trend_growth": trend_growth,
                },
            )

            return record

        except Exception as exc:
            logger.exception(
                "google_trends_collection_failed",
                extra={
                    "keyword": keyword,
                    "country": country,
                    "error": str(exc),
                },
            )
            return None

    async def collect(
        self,
        keyword: str,
        max_results: int = 25,
    ) -> list[dict[str, Any]]:

        records: list[dict[str, Any]] = []

        for country in ("US", "IN"):
            record = self.collect_keyword(
                keyword=keyword,
                country=country,
            )

            if record:
                records.append(record)

        return records