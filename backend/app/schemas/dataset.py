"""
Pydantic schemas for dataset uploads, validation pre-flight, and metadata queries.
"""
from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, Field

from app.bioinformatics.models import ValidationSummary


class DatasetUploadResponse(BaseModel):
    """
    Response schema after a successful VCF dataset upload and server-side validation.
    """
    dataset_id: str = Field(..., description="Unique UUID identifying the uploaded dataset")
    original_filename: str = Field(..., description="Original client-side filename")
    stored_filename: str = Field(..., description="Sanitized, collision-free internal filename")
    file_checksum: str = Field(..., description="SHA-256 integrity checksum")
    file_size_bytes: int = Field(..., description="Total file size in bytes")
    assembly: str = Field(..., description="Genome assembly (e.g. GRCh38 or GRCh37)")
    validation_summary: ValidationSummary = Field(..., description="Detailed VCF validation metrics")
    uploaded_at: str = Field(..., description="ISO 8601 upload timestamp")
    message: str = Field("Dataset uploaded and validated successfully.", description="Status message")


class ValidationOnlyResponse(BaseModel):
    """
    Response schema for pre-flight validation without persistent file storage.
    """
    filename: str = Field(..., description="Name of the inspected file")
    assembly: str = Field(..., description="Confirmed or inferred reference genome assembly")
    validation_summary: ValidationSummary = Field(..., description="VCF validation details")
    can_proceed_to_analysis: bool = Field(..., description="True if valid and contains accepted variants")


class DatasetListItem(BaseModel):
    """
    Summary item schema for dataset listings.
    """
    dataset_id: str
    original_filename: str
    file_size_bytes: int
    assembly: str
    is_valid: bool
    variant_count: int
    uploaded_at: str


class DatasetListResponse(BaseModel):
    """
    List of uploaded datasets.
    """
    total: int
    items: List[DatasetListItem]


class ErrorResponse(BaseModel):
    """
    Standard error response contract across all APIs.
    """
    detail: str = Field(..., description="Human-readable error explanation")
    error_code: str = Field(..., description="Standardized application error code")
    timestamp: str = Field(..., description="ISO 8601 error occurrence timestamp")
