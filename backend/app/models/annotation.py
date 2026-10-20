"""
SQLAlchemy annotation entity representing consequence annotations from Ensembl VEP.
"""
import uuid
from datetime import datetime
from typing import Optional
from sqlalchemy import DateTime, ForeignKey, JSON, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, utc_now


class Annotation(Base):
    __tablename__ = "annotations"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    variant_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("variants.id", ondelete="CASCADE"), nullable=False, index=True
    )
    gene_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, index=True)
    gene_symbol: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, index=True)
    transcript_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    consequence: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    impact: Mapped[str] = mapped_column(String(20), nullable=False, default="MODIFIER")
    annotation_source: Mapped[str] = mapped_column(String(64), default="Ensembl VEP", nullable=False)
    annotation_version: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    raw_result_json: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)

    variant = relationship("Variant", back_populates="annotations")
