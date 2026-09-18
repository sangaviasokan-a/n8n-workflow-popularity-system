from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.database import Base


class Source(Base):
    __tablename__ = "sources"

    id: Mapped[int] = mapped_column(
        primary_key=True,
        autoincrement=True,
    )

    workflow_id: Mapped[int] = mapped_column(
        ForeignKey("workflows.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    platform: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        index=True,
    )

    source_id: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )

    url: Mapped[str] = mapped_column(
        String(1000),
        nullable=False,
    )

    # Country belongs to the evidence/source, not necessarily
    # to the canonical workflow.
    #
    # Examples:
    #   Google Trends US -> US
    #   Google Trends India -> IN
    #   YouTube -> NULL if audience country is unknown
    #   Forum -> NULL if country is unknown
    country: Mapped[str | None] = mapped_column(
        String(2),
        nullable=True,
        index=True,
    )

    published_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    discovered_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=datetime.utcnow,
        nullable=False,
    )

    workflow: Mapped["Workflow"] = relationship(
        "Workflow",
        back_populates="sources",
    )

    metrics: Mapped[list["Metric"]] = relationship(
        "Metric",
        back_populates="source",
        cascade="all, delete-orphan",
    )

    __table_args__ = (
        UniqueConstraint(
            "platform",
            "source_id",
            name="uq_source_platform_source_id",
        ),
    )