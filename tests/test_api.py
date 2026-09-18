from fastapi.testclient import TestClient

from app.database.repository import (
    _safe_float,
    _safe_int,
)
from app.main import app


client = TestClient(app)


def test_root():
    response = client.get("/")

    assert response.status_code == 200

    data = response.json()

    assert data["status"] == "running"
    assert data["version"] == "0.1.0"


def test_health():
    response = client.get("/health")

    assert response.status_code == 200

    data = response.json()

    assert "status" in data
    assert "database" in data


def test_missing_integer_metric_stays_none():
    assert _safe_int(None) is None


def test_real_zero_integer_metric_stays_zero():
    assert _safe_int(0) == 0


def test_missing_float_metric_stays_none():
    assert _safe_float(None) is None


def test_real_zero_float_metric_stays_zero():
    assert _safe_float(0) == 0.0


def test_invalid_integer_metric_stays_none():
    assert _safe_int("invalid") is None


def test_invalid_float_metric_stays_none():
    assert _safe_float("invalid") is None


def test_workflow_history_includes_all_metric_fields():
    response = client.get(
        "/workflows/54/history"
    )

    # Database-backed test environments may not have seed data.
    if response.status_code == 404:
        return

    assert response.status_code == 200

    data = response.json()

    assert "workflow_id" in data
    assert "title" in data
    assert "history" in data

    if data["history"]:

        item = data["history"][0]

        for field in (
            "views",
            "likes",
            "comments",
            "replies",
            "contributors",
            "likes_per_view",
            "comments_per_view",
            "popularity_score",
            "confidence_score",
            "search_interest",
            "average_interest",
            "maximum_interest",
            "trend_growth",
        ):
            assert field in item