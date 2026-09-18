from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class MetricResponse(BaseModel):
    """
    Historical metric snapshot for a source.

    None means the source did not provide that metric.
    """

    model_config = ConfigDict(
        from_attributes=True
    )

    id: int

    views: int | None = Field(
        default=None,
        ge=0,
    )

    likes: int | None = Field(
        default=None,
        ge=0,
    )

    comments: int | None = Field(
        default=None,
        ge=0,
    )

    replies: int | None = Field(
        default=None,
        ge=0,
    )

    contributors: int | None = Field(
        default=None,
        ge=0,
    )

    likes_per_view: float | None = Field(
        default=None,
        ge=0,
    )

    comments_per_view: float | None = Field(
        default=None,
        ge=0,
    )

    # Calculated values remain non-null.
    popularity_score: float = Field(
        ge=0,
        le=100,
    )

    confidence_score: float = Field(
        ge=0,
        le=100,
    )

    captured_at: datetime

    search_interest: float | None = Field(
        default=None,
        ge=0,
        le=100,
    )

    average_interest: float | None = Field(
        default=None,
        ge=0,
        le=100,
    )

    maximum_interest: float | None = Field(
        default=None,
        ge=0,
        le=100,
    )

    trend_growth: float | None = None


class HistoryMetricResponse(BaseModel):
    """
    Historical metric returned by the workflow history endpoint.

    None means the metric was unavailable.
    Zero means the source actually reported zero.
    """

    model_config = ConfigDict(
        from_attributes=True
    )

    id: int

    platform: str

    source_id: str

    views: int | None = Field(
        default=None,
        ge=0,
    )

    likes: int | None = Field(
        default=None,
        ge=0,
    )

    comments: int | None = Field(
        default=None,
        ge=0,
    )

    replies: int | None = Field(
        default=None,
        ge=0,
    )

    contributors: int | None = Field(
        default=None,
        ge=0,
    )

    likes_per_view: float | None = Field(
        default=None,
        ge=0,
    )

    comments_per_view: float | None = Field(
        default=None,
        ge=0,
    )

    popularity_score: float = Field(
        ge=0,
        le=100,
    )

    confidence_score: float = Field(
        ge=0,
        le=100,
    )

    captured_at: datetime

    search_interest: float | None = Field(
        default=None,
        ge=0,
        le=100,
    )

    average_interest: float | None = Field(
        default=None,
        ge=0,
        le=100,
    )

    maximum_interest: float | None = Field(
        default=None,
        ge=0,
        le=100,
    )

    trend_growth: float | None = None


class WorkflowHistoryResponse(BaseModel):
    """
    Historical metrics for a workflow.
    """

    workflow_id: int

    title: str

    history: list[
        HistoryMetricResponse
    ]


class SourceResponse(BaseModel):
    """
    Source/evidence information.
    """

    model_config = ConfigDict(
        from_attributes=True
    )

    id: int

    platform: str

    source_id: str

    url: str

    published_at: datetime | None

    discovered_at: datetime

    metrics: list[
        MetricResponse
    ] = Field(
        default_factory=list
    )


class WorkflowResponse(BaseModel):
    """
    Complete workflow response.
    """

    model_config = ConfigDict(
        from_attributes=True
    )

    id: int

    title: str

    normalized_title: str

    description: str | None

    country: str | None

    popularity_score: float = Field(
        ge=0,
        le=100,
    )

    confidence_score: float = Field(
        ge=0,
        le=100,
    )

    evidence_count: int = Field(
        ge=0
    )

    created_at: datetime

    updated_at: datetime

    sources: list[
        SourceResponse
    ] = Field(
        default_factory=list
    )


class WorkflowListResponse(BaseModel):
    """
    Paginated workflow response.
    """

    items: list[
        WorkflowResponse
    ]

    total: int

    page: int = Field(
        ge=1
    )

    page_size: int = Field(
        ge=1,
        le=100,
    )

    pages: int = Field(
        ge=0
    )


class HealthResponse(BaseModel):
    """
    Health-check response.
    """

    status: str

    database: str