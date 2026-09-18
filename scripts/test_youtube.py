import asyncio

from app.collectors.youtube import YouTubeCollector


async def main():
    collector = YouTubeCollector()

    records = await collector.collect(
        queries=[
            "n8n AI agent",
            "n8n workflow",
        ],
        max_results_per_query=5,
    )

    print()
    print("=" * 60)
    print("YOUTUBE COLLECTION RESULT")
    print("=" * 60)
    print(
        f"Records collected: {len(records)}"
    )
    print()

    for record in records:
        print(
            f"Title: {record['title']}"
        )
        print(
            f"Video ID: {record['source_id']}"
        )
        print(
            f"Views: {record['views']}"
        )
        print(
            f"Likes: {record['likes']}"
        )
        print(
            f"Comments: {record['comments']}"
        )
        print(
            f"URL: {record['url']}"
        )
        print("-" * 60)


if __name__ == "__main__":
    asyncio.run(main())