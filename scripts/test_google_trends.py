import asyncio
import logging

from app.collectors.google_trends import GoogleTrendsCollector


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)


async def main() -> None:

    collector = GoogleTrendsCollector(
        request_delay=5.0,
    )

    keywords = [
        "n8n",
        "n8n automation",
    ]

    records = await collector.collect(
        keywords=keywords,
        countries=["US"],
        timeframe="today 12-m",
    )

    print()
    print("=" * 70)
    print("GOOGLE TRENDS RESULTS")
    print("=" * 70)

    print(f"Records collected: {len(records)}")

    for record in records:
        print()
        print(f"Keyword:           {record['title']}")
        print(f"Country:           {record['country']}")
        print(f"Current Interest:  {record['current_interest']}")
        print(f"Average Interest:  {record['average_interest'] if record['average_interest'] is not None else 'N/A'}")
        print(f"Maximum Interest:  {record['maximum_interest']}")
        print(f"Trend Growth:      {record['trend_growth'] if record['trend_growth'] is not None else 'N/A'}%")
        print(f"Source ID:         {record['source_id']}")
        print(f"URL:               {record['url']}")

    print()
    print("=" * 70)


if __name__ == "__main__":
    asyncio.run(main())