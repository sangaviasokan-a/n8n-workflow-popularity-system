from datetime import datetime, timezone

from app.processors.workflow_matcher import assign_workflow_key


def test_cross_platform_titles_generate_same_workflow_key():
    records = [
        {
            "title": "Build an AI Agent with n8n",
            "url": "https://youtube.com/watch?v=test123",
            "platform": "youtube",
            "source_id": "test123",
        },
        {
            "title": "AI Agent n8n Tutorial",
            "url": "https://community.n8n.io/t/test",
            "platform": "forum",
            "source_id": "forum-test",
        },
        {
            "title": "n8n AI Agent",
            "url": "https://trends.google.com/test",
            "platform": "google",
            "source_id": "google-test",
        },
    ]

    processed = [assign_workflow_key(record.copy()) for record in records]

    keys = {record["workflow_key"] for record in processed}

    assert len(keys) == 1
    
    assert processed[0]["workflow_key"] == "n8n ai agent"