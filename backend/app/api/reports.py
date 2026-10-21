"""
REST API Router for Audit-Ready PDF Report Generation, Listing, and Streaming Downloads.
"""
from pathlib import Path
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.dataset import ErrorResponse
from app.schemas.report import ReportListResponse, ReportResponse
from app.services.report_service import report_service

router = APIRouter()


@router.post(
    "/analyses/{analysis_id}/reports",
    response_model=ReportResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Generate PDF analysis report",
    description="Synthesizes analysis coordinates, VEP functional consequences, ClinVar evidence, and AI explanations into an audit-ready PDF document.",
    responses={
        400: {"model": ErrorResponse, "description": "Analysis is not finished"},
        404: {"model": ErrorResponse, "description": "Analysis or dataset not found"},
        500: {"model": ErrorResponse, "description": "PDF generation failed"},
    },
)
async def generate_analysis_report(
    analysis_id: str,
    db: Session = Depends(get_db),
):
    return report_service.generate_report(db, analysis_id)


@router.get(
    "/analyses/{analysis_id}/reports",
    response_model=ReportListResponse,
    summary="List generated reports for an analysis",
    description="Retrieves a list of all previously generated PDF reports for a given genomic analysis.",
    responses={
        404: {"model": ErrorResponse, "description": "Analysis job not found"},
    },
)
async def list_analysis_reports(
    analysis_id: str,
    db: Session = Depends(get_db),
):
    return report_service.list_reports(db, analysis_id)


@router.get(
    "/analyses/{analysis_id}/report/download",
    summary="Download latest analysis report PDF",
    description="Streams the most recent PDF report for an analysis. If none exists and the job is complete, automatically renders one.",
    responses={
        400: {"model": ErrorResponse, "description": "Analysis not ready for reporting"},
        404: {"model": ErrorResponse, "description": "Analysis not found"},
    },
)
async def download_latest_report(
    analysis_id: str,
    db: Session = Depends(get_db),
):
    report = report_service.get_latest_report_for_analysis(db, analysis_id)
    filename = Path(report.report_path).name
    return FileResponse(
        path=report.report_path,
        filename=filename,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get(
    "/reports/{report_id}/download",
    summary="Download specific report PDF",
    description="Streams a specific generated PDF report document by report ID.",
    responses={
        404: {"model": ErrorResponse, "description": "Report not found"},
    },
)
async def download_report_by_id(
    report_id: str,
    db: Session = Depends(get_db),
):
    report = report_service.get_report(db, report_id)
    filename = Path(report.report_path).name
    return FileResponse(
        path=report.report_path,
        filename=filename,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )

