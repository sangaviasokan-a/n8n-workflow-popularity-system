from __future__ import annotations

import pytest

from app.collectors.youtube import (
    YouTubeCollector,
)


def test_normalize_video():
    item = {
        "id": "abc123",
        "snippet": {
            "title": "Build n8n AI Agent",
            "description": "n8n automation tutorial",
            "publishedAt": "2026-09-10T10:00:00Z",
        },
        "statistics": {
            "viewCount": "10000",
            "likeCount": "500",
            "commentCount": "100",
        },
    }

    record = (
        YouTubeCollector._normalize_video(
            item
        )
    )

    assert record is not None

    assert record["platform"] == "youtube"
    assert record["source_id"] == "abc123"
    assert record["video_id"] == "abc123"

    assert (
        record["title"]
        == "Build n8n AI Agent"
    )

    assert record["views"] == 10000
    assert record["likes"] == 500
    assert record["comments"] == 100

    assert (
        record["url"]
        == "https://www.youtube.com/watch?v=abc123"
    )

    # Audience country must not be fabricated.
    assert record["country"] is None


def test_normalize_video_missing_id():
    item = {
        "id": "",
        "snippet": {
            "title": "n8n automation",
        },
        "statistics": {},
    }

    record = (
        YouTubeCollector._normalize_video(
            item
        )
    )

    assert record is None


def test_normalize_video_missing_title():
    item = {
        "id": "abc123",
        "snippet": {
            "title": "",
        },
        "statistics": {},
    }

    record = (
        YouTubeCollector._normalize_video(
            item
        )
    )

    assert record is None


def test_normalize_video_missing_statistics():
    item = {
        "id": "abc123",
        "snippet": {
            "title": "n8n automation",
        },
    }

    record = (
        YouTubeCollector._normalize_video(
            item
        )
    )

    assert record is not None

    assert record["views"] == 0
    assert record["likes"] == 0
    assert record["comments"] == 0


@pytest.mark.asyncio
async def test_search_videos(monkeypatch):
    collector = YouTubeCollector(
        api_key="test-key"
    )

    async def fake_request(
        endpoint,
        params,
    ):
        assert endpoint == "search"

        assert (
            params["q"]
            == "n8n workflow"
        )

        return {
            "items": [
                {
                    "id": {
                        "videoId": "abc123"
                    },
                    "snippet": {
                        "title": "n8n workflow",
                    },
                }
            ]
        }

    monkeypatch.setattr(
        collector,
        "_request",
        fake_request,
    )

    result = await collector.search_videos(
        "n8n workflow"
    )

    assert len(
        result["items"]
    ) == 1

    assert (
        result["items"][0]["id"]["videoId"]
        == "abc123"
    )


@pytest.mark.asyncio
async def test_get_video_details(monkeypatch):
    collector = YouTubeCollector(
        api_key="test-key"
    )

    async def fake_request(
        endpoint,
        params,
    ):
        assert endpoint == "videos"

        assert (
            params["id"]
            == "abc123,def456"
        )

        return {
            "items": [
                {
                    "id": "abc123",
                    "snippet": {
                        "title": "n8n AI Agent",
                    },
                    "statistics": {
                        "viewCount": "100",
                    },
                }
            ]
        }

    monkeypatch.setattr(
        collector,
        "_request",
        fake_request,
    )

    result = await collector.get_video_details(
        [
            "abc123",
            "def456",
        ]
    )

    assert len(
        result["items"]
    ) == 1


@pytest.mark.asyncio
async def test_collect_deduplicates_video_ids(
    monkeypatch,
):
    collector = YouTubeCollector(
        api_key="test-key"
    )

    async def fake_search(
        query,
        max_results=25,
        page_token=None,
    ):
        return {
            "items": [
                {
                    "id": {
                        "videoId": "same-video"
                    },
                    "snippet": {},
                }
            ]
        }

    async def fake_details(
        video_ids,
    ):
        return {
            "items": [
                {
                    "id": video_ids[0],
                    "snippet": {
                        "title": "n8n AI Agent",
                    },
                    "statistics": {
                        "viewCount": "1000",
                        "likeCount": "50",
                        "commentCount": "10",
                    },
                }
            ]
        }

    monkeypatch.setattr(
        collector,
        "search_videos",
        fake_search,
    )

    monkeypatch.setattr(
        collector,
        "get_video_details",
        fake_details,
    )

    records = await collector.collect(
        queries=[
            "n8n AI agent",
            "n8n automation",
        ]
    )

    assert len(records) == 1
    assert (
        records[0]["source_id"]
        == "same-video"
    )
