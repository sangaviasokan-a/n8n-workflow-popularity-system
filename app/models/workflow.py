from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Float, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.database import Base


class Workflow(Base):
    __tablename__ = "workflows"

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        autoincrement=True,
    )

    title: Mapped[str] = mapped_column(
        String(500),
        nullable=False,
        index=True,
    )

    # Human-readable normalized title.
    normalized_title: Mapped[str] = mapped_column(
        String(500),
        nullable=False,
        index=True,
    )

    # Stable canonical identity used for cross-platform matching.
    #
    # Example:
    #   "Build AI Agents with n8n"
    #   "n8n AI Agent Tutorial"
    #   "n8n AI agent"
    #
    # can all resolve to:
    #   "n8n ai agent"
    workflow_key: Mapped[str] = mapped_column(
        String(500),
        nullable=False,
        index=True,
    )

    description: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    # Kept for backward compatibility with the existing database.
    #
    # Country-specific evidence is now stored on Source.country.
    country: Mapped[str | None] = mapped_column(
        String(2),
        nullable=True,
        index=True,
    )

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

    evidence_count: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=datetime.utcnow,
        nullable=False,
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False,
    )

    sources: Mapped[list["Source"]] = relationship(
        "Source",
        back_populates="workflow",
        cascade="all, delete-orphan",
    )