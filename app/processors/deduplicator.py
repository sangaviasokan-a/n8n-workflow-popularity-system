from __future__ import annotations

from typing import Any


class Deduplicator:
    """
    Removes duplicate source records.

    Primary identity:
        platform + source_id

    Collector-specific fallback IDs:
        YouTube -> video_id
        Forum   -> topic_id
        Google  -> keyword
    """

    @staticmethod
    def deduplicate(
        records: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:

        unique: dict[
            tuple[str, str],
            dict[str, Any],
        ] = {}

        for record in records:

            if not isinstance(record, dict):
                continue

            platform = str(
                record.get(
                    "platform",
                    "",
                )
            ).strip().lower()

            # ------------------------------------------------------
            # Resolve source ID
            # ------------------------------------------------------

            source_id = record.get("source_id")

            if not source_id:

                if platform == "youtube":
                    source_id = record.get(
                        "video_id"
                    )

                elif platform == "forum":
                    source_id = record.get(
                        "topic_id"
                    )

                elif platform == "google":
                    source_id = record.get(
                        "keyword"
                    )

            if source_id:

                source_id = str(
                    source_id
                ).strip()

                key = (
                    platform,
                    source_id,
                )

            else:

                # --------------------------------------------------
                # Fallback identity
                # --------------------------------------------------

                normalized_title = str(
                    record.get(
                        "normalized_title",
                        record.get(
                            "title",
                            "",
                        ),
                    )
                ).strip().lower()

                url = str(
                    record.get(
                        "url",
                        "",
                    )
                ).strip()

                key = (
                    platform,
                    f"{normalized_title}:{url}",
                )

            if key not in unique:

                unique[key] = dict(record)

                # Preserve canonical source_id when possible.
                if source_id and not unique[key].get(
                    "source_id"
                ):
                    unique[key]["source_id"] = source_id

        return list(
            unique.values()
        )


def deduplicate_records(
    records: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """
    Compatibility wrapper for the processing pipeline.
    """

    return Deduplicator.deduplicate(records)