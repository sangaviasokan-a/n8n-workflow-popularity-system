from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, Integer
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.database import Base


class Metric(Base):
    __tablename__ = "metrics"

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        autoincrement=True,
    )

    source_id: Mapped[int] = mapped_column(
        ForeignKey("sources.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # ----------------------------------------------------------
    # Raw engagement metrics
    #
    # None = metric was unavailable/not supplied
    # 0    = metric was actually zero
    # ----------------------------------------------------------

    views: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
        default=None,
    )

    likes: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
        default=None,
    )

    comments: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
        default=None,
    )

    replies: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
        default=None,
    )

    contributors: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
        default=None,
    )

    # ----------------------------------------------------------
    # Derived engagement ratios
    #
    # None = cannot be calculated because source metric
    #        was unavailable
    # ----------------------------------------------------------

    likes_per_view: Mapped[float | None] = mapped_column(
        Float,
        nullable=True,
        default=None,
    )

    comments_per_view: Mapped[float | None] = mapped_column(
        Float,
        nullable=True,
        default=None,
    )

    # ----------------------------------------------------------
    # Calculated scores
    #
    # These remain non-null because the scoring system always
    # produces a bounded score.
    # ----------------------------------------------------------

    popularity_score: Mapped[float] = mapped_column(
        Float,
        default=0.0,
        nullable=False,
    )

    confidence_score: Mapped[float] = mapped_column(
        Float,
        default=0.0,
        nullable=False,
    )

    # ----------------------------------------------------------
    # Historical timestamp
    # ----------------------------------------------------------

    captured_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=datetime.utcnow,
        nullable=False,
        index=True,
    )

    # ----------------------------------------------------------
    # Relationship
    # ----------------------------------------------------------

    source: Mapped["Source"] = relationship(
        "Source",
        back_populates="metrics",
    )

    # ----------------------------------------------------------
    # Google Trends metrics
    #
    # None = unavailable
    # 0    = genuine zero returned by Google Trends
    # ----------------------------------------------------------

    search_interest: Mapped[float | None] = mapped_column(
        Float,
        nullable=True,
        default=None,
    )

    average_interest: Mapped[float | None] = mapped_column(
        Float,
        nullable=True,
        default=None,
    )

    maximum_interest: Mapped[float | None] = mapped_column(
        Float,
        nullable=True,
        default=None,
    )

    trend_growth: Mapped[float | None] = mapped_column(
        Float,
        nullable=True,
        default=None,
    )