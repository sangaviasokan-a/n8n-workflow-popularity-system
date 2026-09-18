from __future__ import annotations

from math import ceil

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.database.database import get_db
from app.models import Source, Workflow
from app.schemas.workflow import (
    WorkflowHistoryResponse,
    WorkflowListResponse,
    WorkflowResponse,
)

router = APIRouter(prefix="/workflows", tags=["Workflows"])


def _get_platform_workflows(
    platform: str,
    page: int,
    page_size: int,
    country: str | None,
    sort_by: str,
    db: Session,
) -> WorkflowListResponse:

    query = (
        select(Workflow)
        .options(
            selectinload(Workflow.sources)
            .selectinload(Source.metrics)
        )
        .where(
            Workflow.sources.any(
                Source.platform == platform
            )
        )
    )

    count_query = (
        select(func.count())
        .select_from(Workflow)
        .where(
            Workflow.sources.any(
                Source.platform == platform
            )
        )
    )

    # Country filter
    if country:
        country = country.upper()

        query = query.where(
            Workflow.sources.any(Source.country == country)
        )

        count_query = count_query.where(
            Workflow.sources.any(Source.country == country)
        )

    # Sorting
    if sort_by == "popularity":
        query = query.order_by(
            Workflow.popularity_score.desc(),
            Workflow.confidence_score.desc(),
        )

    elif sort_by == "confidence":
        query = query.order_by(
            Workflow.confidence_score.desc(),
            Workflow.popularity_score.desc(),
        )

    elif sort_by == "evidence":
        query = query.order_by(
            Workflow.evidence_count.desc(),
            Workflow.popularity_score.desc(),
        )

    else:
        raise HTTPException(
            status_code=400,
            detail={
                "error": "invalid_sort_by",
                "message": (
                    "sort_by must be "
                    "popularity, confidence, or evidence"
                ),
            },
        )

    # Total records
    total = db.scalar(count_query) or 0

    # Pagination
    offset = (page - 1) * page_size

    workflows = (
        db.scalars(
            query
            .offset(offset)
            .limit(page_size)
        )
        .unique()
        .all()
    )

    pages = ceil(total / page_size) if total else 0

    return WorkflowListResponse(
        items=workflows,
        total=total,
        page=page,
        page_size=page_size,
        pages=pages,
    )


# ---------------------------------------------------------
# ALL WORKFLOWS
# ---------------------------------------------------------

@router.get(
    "",
    response_model=WorkflowListResponse,
)
def get_workflows(
    page: int = Query(
        1,
        ge=1,
        description="Page number",
    ),
    page_size: int = Query(
        20,
        ge=1,
        le=100,
        description="Number of records per page",
    ),
    platform: str | None = Query(
        None,
        description="Filter by platform",
    ),
    country: str | None = Query(
        None,
        description="Filter by country: US or IN",
    ),
    sort_by: str = Query(
        "popularity",
        description="Sort by popularity, confidence, or evidence",
    ),
    db: Session = Depends(get_db),
):
    query = (
        select(Workflow)
        .options(
            selectinload(Workflow.sources)
            .selectinload(Source.metrics)
        )
    )

    count_query = select(
        func.count()
    ).select_from(Workflow)

    # Country filter
    if country:
        country = country.upper()

        query = query.where(
            Workflow.sources.any(Source.country == country)
        )

        count_query = count_query.where(
            Workflow.sources.any(Source.country == country)
        )

    # Platform filter
    if platform:
        platform = platform.lower()

        query = query.where(
            Workflow.sources.any(
                Source.platform == platform
            )
        )

        count_query = count_query.where(
            Workflow.sources.any(
                Source.platform == platform
            )
        )

    # Sorting
    if sort_by == "popularity":
        query = query.order_by(
            Workflow.popularity_score.desc(),
            Workflow.confidence_score.desc(),
        )

    elif sort_by == "confidence":
        query = query.order_by(
            Workflow.confidence_score.desc(),
            Workflow.popularity_score.desc(),
        )

    elif sort_by == "evidence":
        query = query.order_by(
            Workflow.evidence_count.desc(),
            Workflow.popularity_score.desc(),
        )

    else:
        raise HTTPException(
            status_code=400,
            detail={
                "error": "invalid_sort_by",
                "message": (
                    "sort_by must be "
                    "popularity, confidence, or evidence"
                ),
            },
        )

    total = db.scalar(count_query) or 0

    offset = (page - 1) * page_size

    workflows = (
        db.scalars(
            query
            .offset(offset)
            .limit(page_size)
        )
        .unique()
        .all()
    )

    pages = ceil(total / page_size) if total else 0

    return WorkflowListResponse(
        items=workflows,
        total=total,
        page=page,
        page_size=page_size,
        pages=pages,
    )


# ---------------------------------------------------------
# TOP WORKFLOWS
# ---------------------------------------------------------

@router.get(
    "/top",
    response_model=WorkflowListResponse,
)
def get_top_workflows(
    limit: int = Query(
        10,
        ge=1,
        le=100,
        description="Number of top workflows",
    ),
    country: str | None = Query(
        None,
        description="Filter by country: US or IN",
    ),
    db: Session = Depends(get_db),
):
    query = (
        select(Workflow)
        .options(
            selectinload(Workflow.sources)
            .selectinload(Source.metrics)
        )
    )

    if country:
        query = query.where(
            Workflow.sources.any(Source.country == country.upper())
        )

    workflows = (
        db.scalars(
            query
            .order_by(
                Workflow.popularity_score.desc(),
                Workflow.confidence_score.desc(),
            )
            .limit(limit)
        )
        .unique()
        .all()
    )

    return WorkflowListResponse(
        items=workflows,
        total=len(workflows),
        page=1,
        page_size=limit,
        pages=1 if workflows else 0,
    )


# ---------------------------------------------------------
# YOUTUBE WORKFLOWS
# ---------------------------------------------------------

@router.get(
    "/youtube",
    response_model=WorkflowListResponse,
    summary="Get workflows with YouTube evidence",
)
def get_youtube_workflows(
    page: int = Query(
        1,
        ge=1,
        description="Page number",
    ),
    page_size: int = Query(
        20,
        ge=1,
        le=100,
        description="Number of records per page",
    ),
    country: str | None = Query(
        None,
        description="Filter by country: US or IN",
    ),
    sort_by: str = Query(
        "popularity",
        description="Sort by popularity, confidence, or evidence",
    ),
    db: Session = Depends(get_db),
):
    return _get_platform_workflows(
        platform="youtube",
        page=page,
        page_size=page_size,
        country=country,
        sort_by=sort_by,
        db=db,
    )


# ---------------------------------------------------------
# FORUM WORKFLOWS
# ---------------------------------------------------------

@router.get(
    "/forum",
    response_model=WorkflowListResponse,
    summary="Get workflows with n8n Forum evidence",
)
def get_forum_workflows(
    page: int = Query(
        1,
        ge=1,
        description="Page number",
    ),
    page_size: int = Query(
        20,
        ge=1,
        le=100,
        description="Number of records per page",
    ),
    country: str | None = Query(
        None,
        description="Filter by country: US or IN",
    ),
    sort_by: str = Query(
        "popularity",
        description="Sort by popularity, confidence, or evidence",
    ),
    db: Session = Depends(get_db),
):
    return _get_platform_workflows(
        platform="forum",
        page=page,
        page_size=page_size,
        country=country,
        sort_by=sort_by,
        db=db,
    )


# ---------------------------------------------------------
# GOOGLE TRENDS WORKFLOWS
# ---------------------------------------------------------

@router.get(
    "/google",
    response_model=WorkflowListResponse,
    summary="Get workflows with Google Trends evidence",
)
def get_google_workflows(
    page: int = Query(
        1,
        ge=1,
        description="Page number",
    ),
    page_size: int = Query(
        20,
        ge=1,
        le=100,
        description="Number of records per page",
    ),
    country: str | None = Query(
        None,
        description="Filter by country: US or IN",
    ),
    sort_by: str = Query(
        "popularity",
        description="Sort by popularity, confidence, or evidence",
    ),
    db: Session = Depends(get_db),
):
    return _get_platform_workflows(
        platform="google",
        page=page,
        page_size=page_size,
        country=country,
        sort_by=sort_by,
        db=db,
    )


# ---------------------------------------------------------
# WORKFLOW HISTORY
# ---------------------------------------------------------

@router.get(
    "/{workflow_id}/history",
    response_model=WorkflowHistoryResponse,
)
def get_workflow_history(
    workflow_id: int,
    db: Session = Depends(get_db),
):
    workflow = db.scalar(
        select(Workflow)
        .options(
            selectinload(Workflow.sources)
            .selectinload(Source.metrics)
        )
        .where(
            Workflow.id == workflow_id
        )
    )

    if workflow is None:
        raise HTTPException(
            status_code=404,
            detail={
                "error": "workflow_not_found",
                "message": (
                    f"Workflow {workflow_id} "
                    "was not found"
                ),
            },
        )

    history = []

    for source in workflow.sources:
        for metric in source.metrics:
            history.append(
                {
                    "id": metric.id,
                    "platform": source.platform,
                    "source_id": source.source_id,
                    "views": metric.views,
                    "likes": metric.likes,
                    "comments": metric.comments,
                    "replies": metric.replies,
                    "contributors": metric.contributors,
                    "likes_per_view": metric.likes_per_view,
                    "comments_per_view": metric.comments_per_view,
                    "popularity_score": metric.popularity_score,
                    "confidence_score": metric.confidence_score,
                    "captured_at": metric.captured_at,
                    "search_interest": metric.search_interest,
                    "average_interest": metric.average_interest,
                    "maximum_interest": metric.maximum_interest,
                    "trend_growth": metric.trend_growth,
                }
            )

    history.sort(
        key=lambda item: item["captured_at"],
        reverse=True,
    )

    return WorkflowHistoryResponse(
        workflow_id=workflow.id,
        title=workflow.title,
        history=history,
    )


# ---------------------------------------------------------
# SINGLE WORKFLOW
# ---------------------------------------------------------

@router.get(
    "/{workflow_id}",
    response_model=WorkflowResponse,
)
def get_workflow(
    workflow_id: int,
    db: Session = Depends(get_db),
):
    workflow = db.scalar(
        select(Workflow)
        .options(
            selectinload(Workflow.sources)
            .selectinload(Source.metrics)
        )
        .where(
            Workflow.id == workflow_id
        )
    )

    if workflow is None:
        raise HTTPException(
            status_code=404,
            detail={
                "error": "workflow_not_found",
                "message": (
                    f"Workflow {workflow_id} "
                    "was not found"
                ),
            },
        )

    return workflow