"""
SQLAlchemy entity representing candidate variant prioritization results.
"""
import uuid
from datetime import datetime
from typing import Optional
from sqlalchemy import DateTime, Float, ForeignKey, JSON, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, utc_now


class PrioritizationResult(Base):
    __tablename__ = "prioritization_results"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    variant_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("variants.id", ondelete="CASCADE"), nullable=False, unique=True, index=True
    )
    rule_version: Mapped[str] = mapped_column(String(32), default="v1.0", nullable=False)
    score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    priority_category: Mapped[str] = mapped_column(String(32), nullable=False)
    reasons_json: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    limitations_json: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)

    variant = relationship("Variant", back_populates="prioritization")
