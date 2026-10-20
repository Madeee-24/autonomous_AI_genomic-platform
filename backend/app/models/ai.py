"""
SQLAlchemy entity representing evidence-grounded AI explanations.
"""
import uuid
from datetime import datetime
from typing import Optional
from sqlalchemy import DateTime, ForeignKey, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, utc_now


class AIExplanation(Base):
    __tablename__ = "ai_explanations"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    variant_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("variants.id", ondelete="CASCADE"), nullable=False, unique=True, index=True
    )
    model_provider: Mapped[str] = mapped_column(String(64), nullable=False)
    model_name: Mapped[str] = mapped_column(String(64), nullable=False)
    prompt_version: Mapped[str] = mapped_column(String(32), default="v1.0", nullable=False)
    input_evidence_ids: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    explanation_text: Mapped[str] = mapped_column(Text, nullable=False)
    structured_output_json: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    validation_status: Mapped[str] = mapped_column(String(32), default="VALID", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)

    variant = relationship("Variant", back_populates="ai_explanation")
