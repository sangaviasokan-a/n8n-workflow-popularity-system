import asyncio

from app.collectors.forum import ForumCollector


async def main():

    collector = ForumCollector()

    records = await collector.collect(
        keyword="n8n AI agent",
        max_results=10,
    )

    print(f"\nFound {len(records)} forum topics\n")

    for record in records:

        print(
            f"{record['topic_id']} | "
            f"{record['title']} | "
            f"views={record['views']} | "
            f"replies={record['replies']} | "
            f"likes={record['likes']}"
        )


if __name__ == "__main__":
    asyncio.run(main())