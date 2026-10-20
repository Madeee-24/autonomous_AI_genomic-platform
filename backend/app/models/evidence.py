"""
SQLAlchemy entity representing clinical evidence records from NCBI ClinVar.
"""
import uuid
from datetime import datetime
from typing import Optional
from sqlalchemy import Boolean, DateTime, ForeignKey, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, utc_now


class EvidenceRecord(Base):
    __tablename__ = "evidence_records"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    variant_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("variants.id", ondelete="CASCADE"), nullable=False, index=True
    )
    source_name: Mapped[str] = mapped_column(String(64), default="ClinVar", nullable=False)
    source_accession: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, index=True)
    interpretation: Mapped[str] = mapped_column(String(128), nullable=False)
    review_status: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    evidence_summary: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    source_url: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
    has_conflicts: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    retrieved_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    source_version: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    raw_record_json: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)

    variant = relationship("Variant", back_populates="evidence_records")
