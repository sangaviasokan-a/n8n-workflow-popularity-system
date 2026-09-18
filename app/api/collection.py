from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database.database import get_db
from app.services.collector_orchestrator import CollectionOrchestrator

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/collect",
    tags=["Collection"],
)


@router.post(
    "/youtube",
    response_model=dict[str, Any],
)
async def collect_youtube(
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """
    Collect and store n8n workflow data from YouTube.
    """

    logger.info("YouTube collection API request received")

    orchestrator = CollectionOrchestrator()

    result = await orchestrator.collect_youtube(
        db=db
    )

    return {
        "platform": "youtube",
        "collected": result.collected,
        "valid": result.valid,
        "rejected": result.rejected,
        "duplicates_removed": result.duplicates_removed,
        "stored": result.stored,
        "error": result.error,
    }


@router.post(
    "/forum",
    response_model=dict[str, Any],
)
async def collect_forum(
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """
    Collect and store n8n workflow data from the n8n Forum.
    """

    logger.info("Forum collection API request received")

    orchestrator = CollectionOrchestrator()

    result = await orchestrator.collect_forum(
        db=db
    )

    return {
        "platform": "forum",
        "collected": result.collected,
        "valid": result.valid,
        "rejected": result.rejected,
        "duplicates_removed": result.duplicates_removed,
        "stored": result.stored,
        "error": result.error,
    }


@router.post(
    "/google",
    response_model=dict[str, Any],
)
async def collect_google(
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """
    Collect and store n8n workflow data from Google Trends.
    """

    logger.info("Google Trends collection API request received")

    orchestrator = CollectionOrchestrator()

    result = await orchestrator.collect_google(
        db=db
    )

    return {
        "platform": "google",
        "collected": result.collected,
        "valid": result.valid,
        "rejected": result.rejected,
        "duplicates_removed": result.duplicates_removed,
        "stored": result.stored,
        "error": result.error,
    }


@router.post(
    "/run",
    response_model=dict[str, Any],
)
async def run_collection(
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """
    Run the complete collection pipeline.

    This endpoint is retained for compatibility.
    For n8n orchestration, the individual platform
    endpoints should be called sequentially.
    """

    logger.info("Complete collection API request received")

    orchestrator = CollectionOrchestrator()

    return await orchestrator.run(db=db)