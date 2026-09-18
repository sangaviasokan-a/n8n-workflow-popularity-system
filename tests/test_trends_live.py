from app.collectors.trends import (
    GoogleTrendsCollector,
)


if __name__ == "__main__":
    collector = GoogleTrendsCollector()

    records = collector.collect_keyword(
        keyword="n8n AI agent",
        country="US",
    )

    print("\nGoogle Trends result:\n")

    print(records)