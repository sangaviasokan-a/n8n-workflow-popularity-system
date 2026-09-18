from unittest.mock import AsyncMock

import httpx
import pytest

from app.collectors.youtube import YouTubeCollector


def test_calculate_ratios():
    ratios = YouTubeCollector.calculate_ratios(
        views=1000,
        likes=100,
        comments=20,
    )

    assert ratios["likes_per_view"] == 0.1
    assert ratios["comments_per_view"] == 0.02


def test_zero_views():
    ratios = YouTubeCollector.calculate_ratios(
        views=0,
        likes=0,
        comments=0,
    )

    assert ratios["likes_per_view"] == 0.0
    assert ratios["comments_per_view"] == 0.0


def test_valid_statistics():
    assert YouTubeCollector.validate_statistics(
        views=1000,
        likes=100,
        comments=20,
    )


def test_negative_views_invalid():
    assert not YouTubeCollector.validate_statistics(
        views=-1,
        likes=0,
        comments=0,
    )


def test_negative_likes_invalid():
    assert not YouTubeCollector.validate_statistics(
        views=100,
        likes=-1,
        comments=0,
    )


def test_negative_comments_invalid():
    assert not YouTubeCollector.validate_statistics(
        views=100,
        likes=10,
        comments=-1,
    )


def test_likes_greater_than_views_invalid():
    assert not YouTubeCollector.validate_statistics(
        views=100,
        likes=101,
        comments=10,
    )


def test_comments_greater_than_views_invalid():
    assert not YouTubeCollector.validate_statistics(
        views=100,
        likes=10,
        comments=101,
    )


@pytest.mark.asyncio
async def test_search_videos():
    collector = YouTubeCollector(api_key="test-key")

    collector._get = AsyncMock(
        return_value={
            "items": [
                {
                    "id": {
                        "videoId": "abc123"
                    },
                    "snippet": {
                        "title": "Gmail &amp; n8n Automation",
                        "description": "Learn n8n &#39;step by step&#39;",
                        "publishedAt": "2026-09-01T10:00:00Z",
                        "channelId": "channel123",
                        "channelTitle": "Test Channel",
                        "thumbnails": {
                            "high": {
                                "url": "https://example.com/thumb.jpg"
                            }
                        },
                    },
                }
            ]
        }
    )

    results = await collector.search_videos(
        keyword="n8n Gmail automation",
        max_results=5,
    )

    assert len(results) == 1
    assert results[0]["video_id"] == "abc123"

    # Verify HTML entities are decoded.
    assert results[0]["title"] == "Gmail & n8n Automation"
    assert results[0]["description"] == "Learn n8n 'step by step'"

    assert results[0]["keyword"] == "n8n Gmail automation"
    assert results[0]["url"] == "https://www.youtube.com/watch?v=abc123"


@pytest.mark.asyncio
async def test_empty_keyword_returns_empty_list():
    collector = YouTubeCollector(api_key="test-key")

    results = await collector.search_videos(
        keyword="   ",
        max_results=5,
    )

    assert results == []


@pytest.mark.asyncio
async def test_get_video_statistics():
    collector = YouTubeCollector(api_key="test-key")

    collector._get = AsyncMock(
        return_value={
            "items": [
                {
                    "id": "abc123",
                    "statistics": {
                        "viewCount": "10000",
                        "likeCount": "500",
                        "commentCount": "50",
                    },
                }
            ]
        }
    )

    results = await collector.get_video_statistics(
        ["abc123"]
    )

    assert results["abc123"]["views"] == 10000
    assert results["abc123"]["likes"] == 500
    assert results["abc123"]["comments"] == 50


@pytest.mark.asyncio
async def test_get_video_statistics_empty_ids():
    collector = YouTubeCollector(api_key="test-key")

    collector._get = AsyncMock()

    results = await collector.get_video_statistics([])

    assert results == {}

@pytest.mark.asyncio
async def test_collect():
    collector = YouTubeCollector(api_key="test-key")

    collector.search_videos = AsyncMock(
        return_value=[
            {
                "video_id": "abc123",
                "title": "Gmail Automation",
                "description": "n8n Gmail workflow",
                "published_at": "2026-09-01T10:00:00Z",
                "channel_id": "channel123",
                "channel_title": "Test Channel",
                "thumbnail_url": "https://example.com/thumb.jpg",
                "keyword": "n8n Gmail automation",
                "url": "https://www.youtube.com/watch?v=abc123",
            },
            {
                # Duplicate video ID.
                "video_id": "abc123",
                "title": "Gmail Automation Duplicate",
                "description": "duplicate",
                "published_at": "2026-09-01T10:00:00Z",
                "channel_id": "channel123",
                "channel_title": "Test Channel",
                "thumbnail_url": "https://example.com/thumb.jpg",
                "keyword": "n8n Gmail automation",
                "url": "https://www.youtube.com/watch?v=abc123",
            },
        ]
    )

    collector.get_video_statistics = AsyncMock(
        return_value={
            "abc123": {
                "views": 10000,
                "likes": 500,
                "comments": 50,
            }
        }
    )

    results = await collector.collect(
        keyword="n8n Gmail automation",
        max_results=5,
    )

    # Duplicate should be removed.
    assert len(results) == 1

    record = results[0]

    assert record["platform"] == "youtube"
    assert record["video_id"] == "abc123"
    assert record["views"] == 10000
    assert record["likes"] == 500
    assert record["comments"] == 50

    assert record["likes_per_view"] == 0.05
    assert record["comments_per_view"] == 0.005