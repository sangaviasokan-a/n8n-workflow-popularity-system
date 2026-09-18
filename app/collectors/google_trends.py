from __future__ import annotations

import asyncio
import logging
from typing import Any

from pytrends.exceptions import TooManyRequestsError
from pytrends.request import TrendReq

from app.collectors.base import BaseCollector

logger = logging.getLogger(__name__)


class GoogleTrendsCollector(BaseCollector):
    """
    Google Trends collector.

    Collects search-interest evidence for workflow-related keywords
    across the supported countries: US and IN.

    Important data semantics:

        None
            Metric was unavailable or could not be interpreted.

        0
            Google Trends actually returned a numeric zero.

    Google Trends values are relative scores from 0-100.

    Country is taken directly from the Google Trends geo parameter.

    HTTP 429 responses are handled gracefully.

    Google Trends failure must not stop the complete pipeline.
    """

    platform = "google"

    SUPPORTED_COUNTRIES = {"US", "IN"}
    MAX_KEYWORDS_PER_REQUEST = 5

    def __init__(
        self,
        request_delay: float = 10.0,
    ) -> None:
        self.request_delay = max(
            0.0,
            request_delay,
        )

    # ------------------------------------------------------------------
    # Utility methods
    # ------------------------------------------------------------------

    @staticmethod
    def _safe_interest(
        value: Any,
    ) -> float | None:
        """
        Convert Google Trends interest to a safe 0-100 float.

        None means the value was unavailable or invalid.

        A genuine numeric 0 remains 0.
        """

        if value is None:
            return None

        try:
            value = float(value)

        except (
            TypeError,
            ValueError,
        ):
            return None

        # NaN check
        if value != value:
            return None

        return max(
            0.0,
            min(100.0, value),
        )

    @staticmethod
    def _calculate_growth(
        values: list[float],
    ) -> float | None:
        """
        Calculate percentage growth between the first and last
        available Google Trends values.

        None is returned when there is insufficient usable
        historical data.

        A genuine zero growth remains 0.
        """

        if len(values) < 2:
            return None

        first = values[0]
        last = values[-1]

        # Cannot calculate percentage growth from zero baseline.
        if first <= 0:
            return None

        growth = (
            (last - first)
            / first
        ) * 100.0

        # Avoid invalid values.
        if growth != growth:
            return None

        return growth

    @staticmethod
    def _create_client() -> TrendReq:
        """
        Create a pytrends client.

        Retries are intentionally disabled because repeated
        requests can make Google's 429 rate limiting worse.
        """

        return TrendReq(
            hl="en-US",
            tz=330,
            timeout=(10, 30),
            retries=0,
            backoff_factor=0,
        )

    # ------------------------------------------------------------------
    # Single batch request
    # ------------------------------------------------------------------

    async def _fetch_batch(
        self,
        keywords: list[str],
        country: str,
        timeframe: str = "today 12-m",
    ) -> list[dict[str, Any]]:
        """
        Fetch one batch of Google Trends data.

        Blocking pytrends calls are executed inside
        asyncio.to_thread().
        """

        if not keywords:
            return []

        country = country.upper().strip()

        if country not in self.SUPPORTED_COUNTRIES:
            logger.warning(
                "Unsupported Google Trends country",
                extra={
                    "country": country,
                    "supported_countries": sorted(
                        self.SUPPORTED_COUNTRIES
                    ),
                },
            )
            return []

        try:
            logger.info(
                "Fetching Google Trends data",
                extra={
                    "country": country,
                    "keywords": keywords,
                    "timeframe": timeframe,
                },
            )

            pytrends = self._create_client()

            # ----------------------------------------------------------
            # Build request
            # ----------------------------------------------------------

            await asyncio.to_thread(
                pytrends.build_payload,
                kw_list=keywords,
                timeframe=timeframe,
                geo=country,
                gprop="",
            )

            # ----------------------------------------------------------
            # Fetch interest data
            # ----------------------------------------------------------

            df = await asyncio.to_thread(
                pytrends.interest_over_time
            )

            if df is None or df.empty:
                logger.warning(
                    "Google Trends returned no data",
                    extra={
                        "country": country,
                        "keywords": keywords,
                    },
                )
                return []

            records: list[dict[str, Any]] = []

            # ----------------------------------------------------------
            # Process each keyword
            # ----------------------------------------------------------

            for keyword in keywords:

                if keyword not in df.columns:
                    logger.warning(
                        "Keyword missing from Google Trends response",
                        extra={
                            "country": country,
                            "keyword": keyword,
                        },
                    )
                    continue

                series = df[keyword].dropna()

                if series.empty:
                    logger.warning(
                        "Empty Google Trends series",
                        extra={
                            "country": country,
                            "keyword": keyword,
                        },
                    )
                    continue

                # ------------------------------------------------------
                # Preserve actual zero values.
                #
                # Invalid/NaN values are excluded instead of becoming 0.
                # ------------------------------------------------------

                values: list[float] = []

                for raw_value in series.tolist():

                    safe_value = self._safe_interest(
                        raw_value
                    )

                    if safe_value is None:
                        continue

                    values.append(
                        safe_value
                    )

                if not values:
                    logger.warning(
                        "Google Trends series contains no usable values",
                        extra={
                            "country": country,
                            "keyword": keyword,
                        },
                    )
                    continue

                # ------------------------------------------------------
                # Metrics
                # ------------------------------------------------------

                current_interest = values[-1]

                average_interest = (
                    sum(values)
                    / len(values)
                )

                maximum_interest = max(
                    values
                )

                trend_growth = (
                    self._calculate_growth(
                        values
                    )
                )

                # ------------------------------------------------------
                # Stable source ID
                # ------------------------------------------------------

                source_id = (
                    f"{country}:"
                    f"{keyword.strip().lower()}"
                )

                # ------------------------------------------------------
                # Record
                # ------------------------------------------------------

                record: dict[str, Any] = {
                    "platform": "google",
                    "source_id": source_id,
                    "title": keyword.strip(),
                    "description": (
                        "Google Trends evidence for "
                        f"{keyword.strip()}"
                    ),
                    "url": "https://trends.google.com/",
                    "country": country,
                    "current_interest": current_interest,
                    "average_interest": average_interest,
                    "maximum_interest": maximum_interest,
                    "trend_growth": trend_growth,
                }

                records.append(
                    record
                )

            logger.info(
                "Google Trends batch completed",
                extra={
                    "country": country,
                    "keywords": keywords,
                    "records": len(records),
                },
            )

            return records

        except TooManyRequestsError as exc:

            logger.warning(
                "Google Trends rate limited request (HTTP 429)",
                extra={
                    "country": country,
                    "keywords": keywords,
                    "error": str(exc),
                },
            )

            return []

        except Exception as exc:

            logger.warning(
                "Google Trends batch failed",
                extra={
                    "country": country,
                    "keywords": keywords,
                    "error": str(exc),
                },
                exc_info=True,
            )

            return []

    # ------------------------------------------------------------------
    # Main collection method
    # ------------------------------------------------------------------

    async def collect(
        self,
        keywords: list[str],
        countries: list[str] | None = None,
        timeframe: str = "today 12-m",
    ) -> list[dict[str, Any]]:
        """
        Collect Google Trends records for all requested countries.

        Google Trends supports a maximum of five keywords in one
        comparison request, so keywords are processed in batches.

        If Google blocks a batch with HTTP 429, that batch is skipped
        and collection continues.
        """

        if countries is None:
            countries = [
                "US",
                "IN",
            ]

        # --------------------------------------------------------------
        # Clean keywords
        # --------------------------------------------------------------

        cleaned_keywords: list[str] = []

        seen_keywords: set[str] = set()

        for keyword in keywords:

            if not isinstance(
                keyword,
                str,
            ):
                continue

            keyword = keyword.strip()

            if not keyword:
                continue

            normalized_keyword = (
                keyword.lower()
            )

            if normalized_keyword in seen_keywords:
                continue

            seen_keywords.add(
                normalized_keyword
            )

            cleaned_keywords.append(
                keyword
            )

        if not cleaned_keywords:
            logger.warning(
                "No valid Google Trends keywords supplied"
            )
            return []

        # --------------------------------------------------------------
        # Clean countries
        # --------------------------------------------------------------

        cleaned_countries: list[str] = []

        seen_countries: set[str] = set()

        for country in countries:

            if not isinstance(
                country,
                str,
            ):
                continue

            country = (
                country
                .strip()
                .upper()
            )

            if country not in self.SUPPORTED_COUNTRIES:

                logger.warning(
                    "Skipping unsupported country",
                    extra={
                        "country": country,
                        "supported_countries": sorted(
                            self.SUPPORTED_COUNTRIES
                        ),
                    },
                )

                continue

            if country in seen_countries:
                continue

            seen_countries.add(
                country
            )

            cleaned_countries.append(
                country
            )

        if not cleaned_countries:
            logger.warning(
                "No supported countries supplied"
            )
            return []

        # --------------------------------------------------------------
        # Collect records
        # --------------------------------------------------------------

        records: list[dict[str, Any]] = []

        for country_index, country in enumerate(
            cleaned_countries
        ):

            logger.info(
                "Starting Google Trends country collection",
                extra={
                    "country": country,
                    "country_index": country_index + 1,
                    "total_countries": len(
                        cleaned_countries
                    ),
                },
            )

            # ----------------------------------------------------------
            # Google Trends maximum = 5 keywords/request
            # ----------------------------------------------------------

            for start in range(
                0,
                len(cleaned_keywords),
                self.MAX_KEYWORDS_PER_REQUEST,
            ):

                batch = cleaned_keywords[
                    start:
                    start + self.MAX_KEYWORDS_PER_REQUEST
                ]

                logger.info(
                    "Requesting Google Trends batch",
                    extra={
                        "country": country,
                        "keywords": batch,
                        "batch_number": (
                            start
                            // self.MAX_KEYWORDS_PER_REQUEST
                        ) + 1,
                    },
                )

                batch_records = await self._fetch_batch(
                    keywords=batch,
                    country=country,
                    timeframe=timeframe,
                )

                records.extend(
                    batch_records
                )

                # ------------------------------------------------------
                # Delay between batches
                # ------------------------------------------------------

                is_last_batch = (
                    start
                    + self.MAX_KEYWORDS_PER_REQUEST
                    >= len(cleaned_keywords)
                )

                if not is_last_batch:

                    logger.info(
                        "Waiting before next Google Trends batch",
                        extra={
                            "delay_seconds": self.request_delay,
                        },
                    )

                    await asyncio.sleep(
                        self.request_delay
                    )

            # ----------------------------------------------------------
            # Delay between countries
            # ----------------------------------------------------------

            if (
                country_index
                < len(cleaned_countries) - 1
            ):

                logger.info(
                    "Waiting before next Google Trends country",
                    extra={
                        "delay_seconds": self.request_delay,
                    },
                )

                await asyncio.sleep(
                    self.request_delay
                )

        # --------------------------------------------------------------
        # Final deduplication
        # --------------------------------------------------------------

        unique_records: dict[
            str,
            dict[str, Any],
        ] = {}

        for record in records:

            source_id = record.get(
                "source_id"
            )

            if not source_id:
                continue

            unique_records[
                source_id
            ] = record

        final_records = list(
            unique_records.values()
        )

        # --------------------------------------------------------------
        # Summary logging
        # --------------------------------------------------------------

        logger.info(
            "Google Trends collection completed",
            extra={
                "keywords_requested": len(
                    cleaned_keywords
                ),
                "countries_requested": len(
                    cleaned_countries
                ),
                "records_collected": len(
                    final_records
                ),
            },
        )

        return final_records