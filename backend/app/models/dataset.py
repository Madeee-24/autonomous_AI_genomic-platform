"""
SQLAlchemy dataset entity representing uploaded genomic VCF files.
"""
import uuid
from datetime import datetime
from typing import Optional
from sqlalchemy import BigInteger, DateTime, ForeignKey, JSON, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, utc_now


class Dataset(Base):
    __tablename__ = "datasets"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id: Mapped[Optional[str]] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )
    original_filename: Mapped[str] = mapped_column(String(255), nullable=False)
    stored_filename: Mapped[str] = mapped_column(String(255), nullable=False)
    stored_file_path: Mapped[str] = mapped_column(String(512), nullable=False)
    file_checksum: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    file_size_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False)
    assembly: Mapped[str] = mapped_column(String(20), nullable=False, default="GRCh38")
    validation_status: Mapped[str] = mapped_column(String(30), nullable=False, default="VALID")
    validation_summary_json: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)

    def __init__(self, **kwargs):
        kwargs.setdefault("id", str(uuid.uuid4()))
        super().__init__(**kwargs)

    # Relationships
    analyses = relationship("AnalysisJob", back_populates="dataset", cascade="all, delete-orphan")

