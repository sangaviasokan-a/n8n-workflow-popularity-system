import asyncio

from app.collectors.forum import ForumCollector


async def main():
    collector = ForumCollector()

    records = await collector.collect(
        queries=[
            "AI agent",
            "automation",
            "lead generation",
        ],
        max_pages_per_query=1,
    )

    print(f"\nCollected {len(records)} forum topics\n")

    for record in records[:20]:
        print("=" * 80)
        print(f"Title:        {record['title']}")
        print(f"Topic ID:     {record['source_id']}")
        print(f"Views:        {record['views']}")
        print(f"Replies:      {record['replies']}")
        print(f"Likes:        {record['likes']}")
        print(f"Contributors: {record['contributors']}")
        print(f"URL:          {record['url']}")


if __name__ == "__main__":
    asyncio.run(main())