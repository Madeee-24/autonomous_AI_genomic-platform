"""
Pydantic schemas for Audit-Ready PDF Report Generation and Downloads.
"""
from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, Field


class ReportResponse(BaseModel):
    """
    Representation of a generated PDF report document.
    """
    id: str
    analysis_id: str
    user_id: Optional[str] = None
    report_path: str
    report_status: str
    file_size_bytes: Optional[int] = None
    download_url: str
    created_at: str

    model_config = {"from_attributes": True}


class ReportListResponse(BaseModel):
    """
    Paginated or full listing of generated reports for an analysis.
    """
    total: int
    items: List[ReportResponse]

