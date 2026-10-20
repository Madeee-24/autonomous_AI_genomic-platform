"""
Analysis Service: Coordinates pipeline orchestration, stage transitions, and background execution.
"""
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional
from fastapi import BackgroundTasks, HTTPException, status
from sqlalchemy.orm import Session

from app.bioinformatics.vcf_parser import VCFParser
from app.core.logging import logger
from app.db.session import SessionLocal
from app.models.analysis import AnalysisJob
from app.models.variant import Variant
from app.repositories.analysis_repository import analysis_repo
from app.repositories.dataset_repository import dataset_repo
from app.repositories.variant_repository import variant_repo
from app.schemas.analysis import (
    AnalysisCreateRequest,
    AnalysisListResponse,
    AnalysisResponse,
    WorkflowEventResponse,
)
from app.services.dataset_service import dataset_service


class AnalysisService:
    """
    Manages analysis jobs, workflow events, and asynchronous execution.
    """

    def __init__(self, parser: Optional[VCFParser] = None, session_factory=None):
        self.parser = parser or VCFParser()
        self.session_factory = session_factory or SessionLocal

    def create_analysis(
        self,
        db: Session,
        request: AnalysisCreateRequest,
        background_tasks: BackgroundTasks,
        user_id: Optional[str] = None
    ) -> AnalysisResponse:
        """
        Creates and queues an analysis job, triggering asynchronous background execution.
        """
        # 1. Resolve dataset file path
        stored_file_path: Optional[str] = None

        db_dataset = dataset_repo.get(db, request.dataset_id)
        if db_dataset:
            stored_file_path = db_dataset.stored_file_path
        elif request.dataset_id in dataset_service._registry:
            stored_file_path = dataset_service._registry[request.dataset_id]["stored_path"]
        else:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Dataset '{request.dataset_id}' not found."
            )

        if not stored_file_path or not Path(stored_file_path).exists():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Dataset file is missing from storage: {stored_file_path}"
            )

        # 2. Create AnalysisJob entity
        job = AnalysisJob(
            dataset_id=request.dataset_id,
            user_id=user_id,
            status="QUEUED",
            current_stage="QUEUED",
            configuration_json={
                "genome_assembly": request.genome_assembly,
                "options": request.options.model_dump()
            }
        )
        analysis_repo.create(db, job)

        # 3. Log initial event
        analysis_repo.add_event(
            db,
            job_id=job.id,
            stage="QUEUED",
            event_type="JOB_CREATED",
            message=f"Analysis job created for dataset '{request.dataset_id}'.",
            details=request.options.model_dump()
        )

        # 4. Enqueue background execution
        background_tasks.add_task(self.run_pipeline_background, job.id, stored_file_path)

        return self._format_response(job, variants_count=0)

    def run_pipeline_background(self, job_id: str, file_path: str) -> None:
        """
        Background worker executing the genomic pipeline stages:
        QUEUED -> VALIDATING -> PARSING -> PERSISTING -> COMPLETED
        """
        factory = self.session_factory or SessionLocal
        db = factory()
        try:
            logger.info(f"Starting background pipeline execution for job: {job_id}")

            # 1. Transition to VALIDATING / RUNNING
            analysis_repo.update_status(db, job_id=job_id, status="RUNNING", current_stage="VALIDATING")
            analysis_repo.add_event(
                db, job_id=job_id, stage="VALIDATING", event_type="STAGE_STARTED",
                message="Starting VCF validation and coordinate inspection."
            )

            # 2. Transition to PARSING
            analysis_repo.update_status(db, job_id=job_id, status="RUNNING", current_stage="PARSING")
            analysis_repo.add_event(
                db, job_id=job_id, stage="PARSING", event_type="STAGE_STARTED",
                message="Parsing variant records and multiallelic sites."
            )

            parsed_variants, summary = self.parser.parse(file_path, filename=Path(file_path).name)

            if not summary.is_valid and summary.accepted_variants_count == 0:
                raise ValueError("VCF file failed validation during pipeline processing.")

            # 3. Bulk insert parsed variants
            variant_models: List[Variant] = []
            for pv in parsed_variants:
                v = Variant(
                    analysis_id=job_id,
                    chromosome=pv.chromosome,
                    position=pv.position,
                    reference_allele=pv.reference_allele,
                    alternate_allele=pv.alternate_allele,
                    variant_identifier=pv.variant_id,
                    variant_type=pv.variant_type.value,
                    quality=pv.quality,
                    filter_status=pv.filter_status,
                    genotype_json={"gt": pv.genotype} if pv.genotype else None,
                    info_json=pv.info_fields,
                    allele_index=pv.allele_index,
                    is_multiallelic=pv.is_multiallelic
                )
                variant_models.append(v)

            inserted_count = variant_repo.bulk_create(db, variant_models)
            logger.info(f"Persisted {inserted_count} variants for job {job_id}")

            analysis_repo.add_event(
                db, job_id=job_id, stage="PARSING", event_type="STAGE_COMPLETED",
                message=f"Successfully extracted and stored {inserted_count} variant coordinates.",
                details={"variants_count": inserted_count, "multiallelic_expanded": len(parsed_variants)}
            )

            # 4. Mark COMPLETED (or COMPLETED_WITH_WARNINGS)
            final_status = "COMPLETED_WITH_WARNINGS" if summary.warnings else "COMPLETED"
            analysis_repo.update_status(db, job_id=job_id, status=final_status, current_stage="FINISHED")
            analysis_repo.add_event(
                db, job_id=job_id, stage="FINISHED", event_type="JOB_COMPLETED",
                message=f"Analysis pipeline finished with status: {final_status}."
            )

        except Exception as e:
            logger.error(f"Pipeline execution failed for job {job_id}: {str(e)}", exc_info=True)
            analysis_repo.update_status(
                db, job_id=job_id, status="FAILED", current_stage="FAILED",
                error_code="PIPELINE_ERROR", error_summary=str(e)
            )
            analysis_repo.add_event(
                db, job_id=job_id, stage="FAILED", event_type="JOB_FAILED",
                message=f"Pipeline aborted: {str(e)}"
            )
        finally:
            db.close()

    def get_analysis(self, db: Session, job_id: str) -> AnalysisResponse:
        """
        Retrieves current analysis state and variant count.
        """
        job = analysis_repo.get(db, job_id)
        if not job:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Analysis job '{job_id}' not found."
            )
        _, count = variant_repo.get_by_analysis(db, job_id, limit=1)
        return self._format_response(job, variants_count=count)

    def list_analyses(self, db: Session, skip: int = 0, limit: int = 50) -> AnalysisListResponse:
        """
        Lists all analysis jobs ordered by creation timestamp.
        """
        jobs = analysis_repo.get_multi(db, skip=skip, limit=limit)
        items: List[AnalysisResponse] = []
        for j in jobs:
            _, count = variant_repo.get_by_analysis(db, j.id, limit=1)
            items.append(self._format_response(j, variants_count=count))
        return AnalysisListResponse(total=len(items), items=items)

    def cancel_analysis(self, db: Session, job_id: str) -> AnalysisResponse:
        """
        Cancels a queued or running analysis.
        """
        job = analysis_repo.get(db, job_id)
        if not job:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Analysis job '{job_id}' not found."
            )

        if job.status in ["COMPLETED", "FAILED", "CANCELLED"]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Cannot cancel analysis in '{job.status}' state."
            )

        updated = analysis_repo.update_status(
            db, job_id=job_id, status="CANCELLED", current_stage="CANCELLED",
            error_code="USER_CANCELLED", error_summary="Analysis was manually cancelled by user."
        )
        analysis_repo.add_event(
            db, job_id=job_id, stage="CANCELLED", event_type="JOB_CANCELLED",
            message="Analysis cancelled by user request."
        )
        _, count = variant_repo.get_by_analysis(db, job_id, limit=1)
        return self._format_response(updated, variants_count=count)

    def get_events(self, db: Session, job_id: str) -> List[WorkflowEventResponse]:
        """
        Retrieves all workflow stage transitions and audit events for a job.
        """
        job = analysis_repo.get(db, job_id)
        if not job:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Analysis job '{job_id}' not found."
            )
        events = analysis_repo.get_events(db, job_id)
        return [
            WorkflowEventResponse(
                id=e.id,
                stage=e.stage,
                event_type=e.event_type,
                message=e.message,
                details=e.details_json,
                created_at=e.created_at.isoformat()
            )
            for e in events
        ]

    def _format_response(self, job: AnalysisJob, variants_count: int) -> AnalysisResponse:
        return AnalysisResponse(
            id=job.id,
            dataset_id=job.dataset_id,
            status=job.status,
            current_stage=job.current_stage,
            variants_count=variants_count,
            configuration=job.configuration_json,
            created_at=job.created_at.isoformat(),
            started_at=job.started_at.isoformat() if job.started_at else None,
            finished_at=job.finished_at.isoformat() if job.finished_at else None,
            error_code=job.error_code,
            error_summary=job.error_summary
        )


analysis_service = AnalysisService()

