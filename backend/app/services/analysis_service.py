"""
Analysis Service: Coordinates pipeline orchestration, stage transitions, and background execution.
"""
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional
from fastapi import BackgroundTasks, HTTPException, status
from sqlalchemy.orm import Session

from app.ai.explanation_service import ExplanationService, explanation_service
from app.bioinformatics.vcf_parser import VCFParser
from app.bioinformatics.vep_client import EnsemblVEPClient, vep_client
from app.core.logging import logger
from app.db.session import SessionLocal
from app.evidence.clinvar_client import ClinVarClient, clinvar_client
from app.models.ai import AIExplanation
from app.models.analysis import AnalysisJob
from app.models.prioritization import PrioritizationResult
from app.models.variant import Variant
from app.orchestration.stages import StageContext
from app.orchestration.state import WorkflowState
from app.orchestration.workflow import WorkflowOrchestrator, orchestrator
from app.prioritization.prioritizer import VariantPrioritizer, prioritizer
from app.repositories.analysis_repository import analysis_repo
from app.repositories.dataset_repository import dataset_repo
from app.repositories.variant_repository import variant_repo
from app.schemas.analysis import (
    AnalysisCreateRequest,
    AnalysisListResponse,
    AnalysisResponse,
    WorkflowEventResponse,
)
from app.schemas.variant import (
    AIExplanationSummary,
    AnalysisStatisticsResponse,
    AnnotationSummary,
    DashboardSummaryResponse,
    EvidenceSummary,
    PrioritizationSummary,
    VariantDetailResponse,
    VariantItemResponse,
    VariantListResponse,
)
from app.services.dataset_service import dataset_service


class AnalysisService:
    """
    Manages analysis jobs, workflow events, and asynchronous execution.
    """

    def __init__(
        self,
        parser: Optional[VCFParser] = None,
        session_factory=None,
        vep_client_instance: Optional[EnsemblVEPClient] = None,
        clinvar_client_instance: Optional[ClinVarClient] = None,
        prioritizer_instance: Optional[VariantPrioritizer] = None,
        explanation_service_instance: Optional[ExplanationService] = None,
        orchestrator_instance: Optional[WorkflowOrchestrator] = None,
    ):
        self.parser = parser or VCFParser()
        self.session_factory = session_factory or SessionLocal
        self.vep_client = vep_client_instance or vep_client
        self.clinvar_client = clinvar_client_instance or clinvar_client
        self.prioritizer = prioritizer_instance or prioritizer
        self.explanation_service = explanation_service_instance or explanation_service
        self.orchestrator = orchestrator_instance or WorkflowOrchestrator(
            context=StageContext(
                parser=self.parser,
                vep=self.vep_client,
                clinvar=self.clinvar_client,
                prioritizer_inst=self.prioritizer,
                explainer=self.explanation_service,
            )
        )

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
        Background worker executing the autonomous genomic pipeline via WorkflowOrchestrator.
        Handles stage graph progression, checkpoint recovery, bounded retries, and events.
        """
        factory = self.session_factory or SessionLocal
        db = factory()
        try:
            logger.info(f"Starting background pipeline execution for job: {job_id}")
            state = self.orchestrator.load_state_from_job(db, job_id, file_path)
            if not state:
                job = analysis_repo.get(db, job_id)
                if not job:
                    logger.error(f"Analysis job {job_id} not found in database.")
                    return
                cfg = job.configuration_json or {}
                state = self.orchestrator.create_initial_state(
                    analysis_id=job.id,
                    dataset_id=job.dataset_id,
                    file_path=file_path,
                    genome_assembly=cfg.get("genome_assembly", "GRCh38"),
                    options=cfg.get("options", {}),
                )

            self.orchestrator.execute_workflow(db, state)
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

    def resume_analysis(
        self,
        db: Session,
        job_id: str,
        background_tasks: BackgroundTasks,
    ) -> AnalysisResponse:
        """
        Resumes an interrupted or failed analysis from its last recorded stage checkpoint.
        """
        job = analysis_repo.get(db, job_id)
        if not job:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Analysis job '{job_id}' not found."
            )

        if job.status not in ["FAILED", "CANCELLED"]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Cannot resume analysis in '{job.status}' state. Only FAILED or CANCELLED jobs can be resumed."
            )

        stored_file_path: Optional[str] = None
        db_dataset = dataset_repo.get(db, job.dataset_id)
        if db_dataset:
            stored_file_path = db_dataset.stored_file_path
        elif job.dataset_id in dataset_service._registry:
            stored_file_path = dataset_service._registry[job.dataset_id]["stored_path"]

        if not stored_file_path or not Path(stored_file_path).exists():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Dataset file is missing from storage: {stored_file_path}"
            )

        # Update status to QUEUED / RESUMING
        updated_job = analysis_repo.update_status(
            db, job_id=job_id, status="QUEUED", current_stage="RESUMING",
            error_code=None, error_summary=None
        )
        analysis_repo.add_event(
            db, job_id=job_id, stage="RESUMING", event_type="JOB_RESUMED",
            message="Analysis resumed from last recorded checkpoint."
        )

        background_tasks.add_task(self.run_pipeline_background, job.id, stored_file_path)

        _, count = variant_repo.get_by_analysis(db, job_id, limit=1)
        return self._format_response(updated_job, variants_count=count)

    def get_checkpoints(self, db: Session, job_id: str) -> dict:
        """
        Retrieves stage checkpoints and retry metadata for an analysis job.
        """
        job = analysis_repo.get(db, job_id)
        if not job:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Analysis job '{job_id}' not found."
            )
        cfg = job.configuration_json or {}
        checkpoints = cfg.get("checkpoints", {})
        return {
            "analysis_id": job.id,
            "status": job.status,
            "current_stage": job.current_stage,
            "checkpoints": checkpoints,
        }

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

    def _format_variant_item(self, v: Variant) -> VariantItemResponse:
        primary_ann = v.annotations[0] if v.annotations else None
        primary_ev = v.evidence_records[0] if v.evidence_records else None
        prio = v.prioritization

        annotations_summary = [
            AnnotationSummary(
                id=ann.id,
                gene_symbol=ann.gene_symbol,
                gene_id=ann.gene_id,
                transcript_id=ann.transcript_id,
                consequence=ann.consequence,
                impact=ann.impact,
                annotation_source=ann.annotation_source,
                annotation_version=ann.annotation_version,
            )
            for ann in v.annotations
        ]

        evidence_summary = [
            EvidenceSummary(
                id=ev.id,
                source_name=ev.source_name,
                source_accession=ev.source_accession,
                interpretation=ev.interpretation,
                review_status=ev.review_status,
                evidence_summary=ev.evidence_summary,
                source_url=ev.source_url,
                has_conflicts=ev.has_conflicts,
                retrieved_at=ev.retrieved_at,
            )
            for ev in v.evidence_records
        ]

        prio_summary = (
            PrioritizationSummary(
                id=prio.id,
                rule_version=prio.rule_version,
                score=prio.score,
                priority_category=prio.priority_category,
                reasons=prio.reasons_json,
                limitations=prio.limitations_json,
            )
            if prio
            else None
        )

        ai_summary = (
            AIExplanationSummary(
                id=v.ai_explanation.id,
                model_provider=v.ai_explanation.model_provider,
                model_name=v.ai_explanation.model_name,
                prompt_version=v.ai_explanation.prompt_version,
                explanation_text=v.ai_explanation.explanation_text,
                validation_status=v.ai_explanation.validation_status,
                structured_output=v.ai_explanation.structured_output_json,
                created_at=v.ai_explanation.created_at,
            )
            if v.ai_explanation
            else None
        )

        return VariantItemResponse(
            id=v.id,
            analysis_id=v.analysis_id,
            chromosome=v.chromosome,
            position=v.position,
            reference_allele=v.reference_allele,
            alternate_allele=v.alternate_allele,
            variant_identifier=v.variant_identifier,
            variant_type=v.variant_type,
            quality=v.quality,
            filter_status=v.filter_status,
            is_multiallelic=v.is_multiallelic,
            primary_gene=primary_ann.gene_symbol if primary_ann else None,
            primary_consequence=primary_ann.consequence if primary_ann else None,
            primary_impact=primary_ann.impact if primary_ann else None,
            clinvar_interpretation=primary_ev.interpretation if primary_ev else None,
            clinvar_review_status=primary_ev.review_status if primary_ev else None,
            clinvar_accession=primary_ev.source_accession if primary_ev else None,
            has_conflicts=primary_ev.has_conflicts if primary_ev else False,
            priority_category=prio.priority_category if prio else "UNCERTAIN",
            priority_score=prio.score if prio else None,
            annotations=annotations_summary,
            evidence_records=evidence_summary,
            prioritization=prio_summary,
            ai_explanation=ai_summary,
        )

    def get_variants(
        self,
        db: Session,
        job_id: str,
        chromosome: Optional[str] = None,
        gene: Optional[str] = None,
        consequence: Optional[str] = None,
        priority_category: Optional[str] = None,
        has_conflicts: Optional[bool] = None,
        search: Optional[str] = None,
        page: int = 1,
        page_size: int = 50,
    ) -> VariantListResponse:
        """
        Retrieves paginated and filtered variants for an analysis job.
        """
        job = analysis_repo.get(db, job_id)
        if not job:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Analysis job '{job_id}' not found."
            )

        skip = max(0, (page - 1) * page_size)
        variants, total = variant_repo.get_by_analysis(
            db=db,
            analysis_id=job_id,
            chromosome=chromosome,
            gene=gene,
            consequence=consequence,
            priority_category=priority_category,
            has_conflicts=has_conflicts,
            search=search,
            skip=skip,
            limit=page_size,
        )

        total_pages = max(1, (total + page_size - 1) // page_size) if total > 0 else 1
        items = [self._format_variant_item(v) for v in variants]

        return VariantListResponse(
            total=total,
            page=page,
            page_size=page_size,
            total_pages=total_pages,
            items=items,
        )

    def get_variant_detail(self, db: Session, job_id: str, variant_id: str) -> VariantDetailResponse:
        """
        Retrieves full details, annotations, evidence, and scores for a specific variant.
        """
        job = analysis_repo.get(db, job_id)
        if not job:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Analysis job '{job_id}' not found."
            )

        variant = variant_repo.get_variant_detail(db, variant_id)
        if not variant or variant.analysis_id != job_id:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Variant '{variant_id}' not found in analysis '{job_id}'."
            )

        base_item = self._format_variant_item(variant)
        return VariantDetailResponse(
            **base_item.model_dump(),
            info_json=variant.info_json,
            genotype_json=variant.genotype_json,
        )

    def get_statistics(self, db: Session, job_id: str) -> AnalysisStatisticsResponse:
        """
        Retrieves computed summary statistics and distributions for an analysis.
        """
        job = analysis_repo.get(db, job_id)
        if not job:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Analysis job '{job_id}' not found."
            )

        stats = variant_repo.get_statistics(db, job_id)
        return AnalysisStatisticsResponse(**stats)

    def get_dashboard_summary(self, db: Session) -> DashboardSummaryResponse:
        """
        Retrieves system-wide dataset, analysis, and variant counts for the main dashboard.
        """
        summary = variant_repo.get_dashboard_summary(db)
        return DashboardSummaryResponse(**summary)

    async def explain_variant(
        self,
        db: Session,
        job_id: str,
        variant_id: str
    ) -> AIExplanationSummary:
        """
        On-demand explanation generation for a single variant in an analysis.
        """
        job = analysis_repo.get(db, job_id)
        if not job:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Analysis job '{job_id}' not found."
            )

        variant = variant_repo.get_variant_detail(db, variant_id)
        if not variant or variant.analysis_id != job_id:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Variant '{variant_id}' not found in analysis '{job_id}'."
            )

        assembly = job.configuration_json.get("genome_assembly", "GRCh38") if job.configuration_json else "GRCh38"
        result = await self.explanation_service.generate_variant_explanation(
            db=db,
            variant=variant,
            genome_assembly=assembly,
            persist=True
        )

        if not result.is_valid or not result.parsed_output:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"AI explanation generation failed validation: {'; '.join(result.validation_errors or ['Unknown error'])}"
            )

        db.refresh(variant)
        exp = variant.ai_explanation
        return AIExplanationSummary(
            id=exp.id,
            model_provider=exp.model_provider,
            model_name=exp.model_name,
            prompt_version=exp.prompt_version,
            explanation_text=exp.explanation_text,
            validation_status=exp.validation_status,
            structured_output=exp.structured_output_json,
            created_at=exp.created_at,
        )

    def get_variant_explanation(
        self,
        db: Session,
        job_id: str,
        variant_id: str
    ) -> AIExplanationSummary:
        """
        Retrieves existing stored AI explanation for a variant.
        """
        variant = variant_repo.get_variant_detail(db, variant_id)
        if not variant or variant.analysis_id != job_id:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Variant '{variant_id}' not found in analysis '{job_id}'."
            )

        if not variant.ai_explanation:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"No AI explanation has been generated yet for variant '{variant_id}'."
            )

        exp = variant.ai_explanation
        return AIExplanationSummary(
            id=exp.id,
            model_provider=exp.model_provider,
            model_name=exp.model_name,
            prompt_version=exp.prompt_version,
            explanation_text=exp.explanation_text,
            validation_status=exp.validation_status,
            structured_output=exp.structured_output_json,
            created_at=exp.created_at,
        )


analysis_service = AnalysisService()

