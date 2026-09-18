from app.processors.workflow_matcher import (
    assign_workflow_key,
    build_workflow_key,
)


def test_ai_agent_titles_match():

    first = build_workflow_key(
        "How to Build an n8n AI Agent"
    )

    second = build_workflow_key(
        "n8n AI Agent Tutorial"
    )

    assert first == second
    assert first == "n8n ai agent"


def test_gmail_automation_normalization():

    result = build_workflow_key(
        "n8n Gmail Automation"
    )

    assert result == "n8n gmail"


def test_google_sheets_normalization():

    result = build_workflow_key(
        "Complete n8n Google Sheets Workflow"
    )

    assert result == "n8n google sheets"


def test_assign_workflow_key():

    record = {
        "platform": "youtube",
        "title": "Build an AI Agent with n8n",
    }

    result = assign_workflow_key(record)

    assert result["workflow_key"] == "n8n ai agent"


def test_empty_title():

    result = build_workflow_key("")

    assert result == ""