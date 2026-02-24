import datetime
from typing import Any

from sqlalchemy import Float, Integer, String, DateTime, CheckConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy.dialects.sqlite import JSON

class Base(DeclarativeBase):
    pass

class Opportunity(Base):
    __tablename__ = "opportunities"
    
    __table_args__ = (
        CheckConstraint("score >= 0.0 AND score <= 1.0", name="chk_score_range"),
        CheckConstraint("status IN ('new', 'notified', 'dismissed', 'saved')", name="chk_status_enum"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    source_system: Mapped[str] = mapped_column(String, index=True)
    process_id: Mapped[str] = mapped_column(String, unique=True, index=True)
    title: Mapped[str] = mapped_column(String)
    entity_name: Mapped[str] = mapped_column(String)
    description: Mapped[str] = mapped_column(String)
    published_at: Mapped[datetime.datetime | None] = mapped_column(DateTime(timezone=True))
    closing_at: Mapped[datetime.datetime | None] = mapped_column(DateTime(timezone=True))
    budget: Mapped[float | None] = mapped_column(Float)
    location: Mapped[str | None] = mapped_column(String)
    url: Mapped[str] = mapped_column(String)
    
    query_match: Mapped[str] = mapped_column(String)
    score: Mapped[float] = mapped_column(Float)
    match_explain: Mapped[dict[str, Any] | list[Any]] = mapped_column(JSON)
    status: Mapped[str] = mapped_column(String, index=True) # new, notified, dismissed, saved
    fingerprint: Mapped[str] = mapped_column(String, index=True)
    
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), 
        default=lambda: datetime.datetime.now(datetime.timezone.utc)
    )
    updated_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), 
        default=lambda: datetime.datetime.now(datetime.timezone.utc),
        onupdate=lambda: datetime.datetime.now(datetime.timezone.utc)
    )

class Run(Base):
    __tablename__ = "runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    started_at: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime.datetime | None] = mapped_column(DateTime(timezone=True))
    collector: Mapped[str] = mapped_column(String)
    items_collected: Mapped[int] = mapped_column(Integer, default=0)
    items_after_filters: Mapped[int] = mapped_column(Integer, default=0)
    items_new: Mapped[int] = mapped_column(Integer, default=0)
    items_notified: Mapped[int] = mapped_column(Integer, default=0)
    errors: Mapped[dict[str, Any] | list[Any] | None] = mapped_column(JSON)
