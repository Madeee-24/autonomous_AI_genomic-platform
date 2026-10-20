"""
SQLAlchemy variant entity representing individual parsed genomic mutations.
"""
import uuid
from datetime import datetime
from typing import List, Optional
from sqlalchemy import BigInteger, Boolean, DateTime, Float, ForeignKey, JSON, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, utc_now


class Variant(Base):
    __tablename__ = "variants"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    analysis_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("analysis_jobs.id", ondelete="CASCADE"), nullable=False, index=True
    )
    chromosome: Mapped[str] = mapped_column(String(10), nullable=False, index=True)
    position: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    reference_allele: Mapped[str] = mapped_column(String(255), nullable=False)
    alternate_allele: Mapped[str] = mapped_column(String(255), nullable=False)
    variant_identifier: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, index=True)
    variant_type: Mapped[str] = mapped_column(String(20), default="SNV", nullable=False)
    quality: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    filter_status: Mapped[str] = mapped_column(String(50), default="PASS", nullable=False)
    genotype_json: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    info_json: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    allele_index: Mapped[int] = mapped_column(BigInteger, default=1, nullable=False)
    is_multiallelic: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)

    def __init__(self, **kwargs):
        kwargs.setdefault("id", str(uuid.uuid4()))
        super().__init__(**kwargs)

    # Relationships
    analysis = relationship("AnalysisJob", back_populates="variants")
    annotations = relationship("Annotation", back_populates="variant", cascade="all, delete-orphan")
    evidence_records = relationship("EvidenceRecord", back_populates="variant", cascade="all, delete-orphan")
    prioritization = relationship("PrioritizationResult", back_populates="variant", uselist=False, cascade="all, delete-orphan")
    ai_explanation = relationship("AIExplanation", back_populates="variant", uselist=False, cascade="all, delete-orphan")

