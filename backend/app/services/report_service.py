"""
Report Service: Manages generation, persistence, listing, and streaming of audit-ready PDF reports.
"""
from datetime import datetime, timezone
import os
from pathlib import Path
from typing import List, Optional
from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.core.config import settings
from app.core.logging import logger
from app.models.analysis import AnalysisJob
from app.models.dataset import Dataset
from app.models.report import Report
from app.models.variant import Variant
from app.reporting.pdf_generator import GenomicReportGenerator, pdf_generator
from app.repositories.analysis_repository import analysis_repo
from app.repositories.dataset_repository import dataset_repo
from app.repositories.report_repository import report_repo
from app.schemas.report import ReportListResponse, ReportResponse
from app.services.dataset_service import dataset_service


class ReportService:
    def __init__(self, generator: Optional[GenomicReportGenerator] = None):
        self.generator = generator or pdf_generator

    def generate_report(
        self,
        db: Session,
        analysis_id: str,
        user_id: Optional[str] = None,
    ) -> ReportResponse:
        """
        Synthesizes all analysis outputs into a publication-quality, audit-ready PDF document.
        """
        job = analysis_repo.get(db, analysis_id)
        if not job:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Analysis job '{analysis_id}' not found.",
            )

        if job.status not in ["COMPLETED", "COMPLETED_WITH_WARNINGS", "FINISHED"]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Cannot generate report for analysis in '{job.status}' status. Job must be completed first.",
            )

        dataset = dataset_repo.get(db, job.dataset_id)
        if not dataset:
            if job.dataset_id in dataset_service._registry:
                reg = dataset_service._registry[job.dataset_id]
                dataset = Dataset(
                    id=job.dataset_id,
                    original_filename=reg.get("original_filename", "dataset.vcf"),
                    stored_filename=reg.get("stored_filename", "dataset.vcf"),
                    stored_file_path=reg.get("stored_path", ""),
                    file_checksum=reg.get("file_checksum", "dummy_checksum"),
                    file_size_bytes=reg.get("file_size_bytes", 0),
                    assembly=reg.get("assembly", "GRCh38"),
                    validation_status="VALID",
                )
                dataset_repo.create(db, dataset)
            else:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Dataset '{job.dataset_id}' associated with analysis was not found.",
                )

        # Query all variants for this analysis with eager-loaded relational graphs
        stmt = (
            select(Variant)
            .where(Variant.analysis_id == analysis_id)
            .options(
                joinedload(Variant.annotations),
                joinedload(Variant.evidence_records),
                joinedload(Variant.prioritization),
                joinedload(Variant.ai_explanation),
            )
            .order_by(Variant.chromosome, Variant.position)
        )
        variants = list(db.scalars(stmt).unique().all())

        # Determine target PDF file location
        timestamp_str = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        report_filename = f"genomic_report_{analysis_id[:8]}_{timestamp_str}.pdf"
        report_dir = Path(settings.REPORT_DIRECTORY)
        report_dir.mkdir(parents=True, exist_ok=True)
        output_path = str(report_dir / report_filename)

        logger.info(f"Generating PDF audit report for analysis {analysis_id} at {output_path}")

        try:
            self.generator.generate_report(
                output_path=output_path,
                job=job,
                dataset=dataset,
                variants=variants,
            )
        except Exception as e:
            logger.error(f"Failed to generate PDF report for job {analysis_id}: {e}", exc_info=True)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to render PDF report document: {str(e)}",
            )

        report = Report(
            analysis_id=analysis_id,
            user_id=user_id,
            report_path=output_path,
            report_status="GENERATED",
        )
        report_repo.create(db, report)

        # Log audit event
        analysis_repo.add_event(
            db,
            job_id=analysis_id,
            stage="REPORTING",
            event_type="REPORT_GENERATED",
            message=f"Publication-ready PDF report generated successfully: {report_filename}.",
            details={"report_id": report.id, "report_path": output_path},
        )

        return self._format_response(report)

    def get_report(self, db: Session, report_id: str) -> Report:
        """
        Retrieves a Report DB model by ID and verifies physical file existence.
        """
        report = report_repo.get(db, report_id)
        if not report:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Report document '{report_id}' not found.",
            )
        if not os.path.exists(report.report_path):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Report PDF file is missing from filesystem at '{report.report_path}'.",
            )
        return report

    def get_latest_report_for_analysis(self, db: Session, analysis_id: str) -> Report:
        """
        Retrieves the most recent report for an analysis, generating one if not yet present.
        """
        job = analysis_repo.get(db, analysis_id)
        if not job:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Analysis job '{analysis_id}' not found.",
            )

        latest = report_repo.get_latest_by_analysis(db, analysis_id)
        if latest and os.path.exists(latest.report_path):
            return latest

        # Auto-generate if job is finished
        if job.status in ["COMPLETED", "COMPLETED_WITH_WARNINGS", "FINISHED"]:
            res = self.generate_report(db, analysis_id)
            return report_repo.get(db, res.id)

        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"No report available. Analysis is in '{job.status}' status.",
        )

    def list_reports(self, db: Session, analysis_id: str) -> ReportListResponse:
        """
        Lists all generated reports for an analysis.
        """
        reports = report_repo.get_by_analysis(db, analysis_id)
        items = [self._format_response(r) for r in reports]
        return ReportListResponse(total=len(items), items=items)

    def _format_response(self, report: Report) -> ReportResponse:
        size = None
        if report.report_path and os.path.exists(report.report_path):
            try:
                size = os.path.getsize(report.report_path)
            except OSError:
                size = None

        return ReportResponse(
            id=report.id,
            analysis_id=report.analysis_id,
            user_id=report.user_id,
            report_path=report.report_path,
            report_status=report.report_status,
            file_size_bytes=size,
            download_url=f"/api/v1/reports/{report.id}/download",
            created_at=report.created_at.isoformat(),
        )


report_service = ReportService()
