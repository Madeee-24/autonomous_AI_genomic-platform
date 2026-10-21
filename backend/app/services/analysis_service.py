"""
Analysis Service: Coordinates pipeline orchestration, stage transitions, and background execution.
"""
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional
from fastapi import BackgroundTasks, HTTPException, status
from sqlalchemy.orm import Session

from app.bioinformatics.vcf_parser import VCFParser
from app.bioinformatics.vep_client import EnsemblVEPClient, vep_client
from app.core.logging import logger
from app.db.session import SessionLocal
from app.evidence.clinvar_client import ClinVarClient, clinvar_client
from app.models.analysis import AnalysisJob
from app.models.prioritization import PrioritizationResult
from app.models.variant import Variant
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
        prioritizer_instance: Optional[VariantPrioritizer] = None
    ):
        self.parser = parser or VCFParser()
        self.session_factory = session_factory or SessionLocal
        self.vep_client = vep_client_instance or vep_client
        self.clinvar_client = clinvar_client_instance or clinvar_client
        self.prioritizer = prioritizer_instance or prioritizer

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

            # 4. Optional VEP Annotation Stage
            job = analysis_repo.get(db, job_id)
            config = job.configuration_json or {}
            options = config.get("options", {})
            assembly = config.get("genome_assembly", "GRCh38")

            if options.get("annotate_with_vep", False):
                analysis_repo.update_status(db, job_id=job_id, status="RUNNING", current_stage="ANNOTATING")
                analysis_repo.add_event(
                    db, job_id=job_id, stage="ANNOTATING", event_type="STAGE_STARTED",
                    message="Starting variant consequence annotation via Ensembl VEP REST API."
                )
                annotations, vep_warnings = self.vep_client.annotate_variants(variant_models, assembly=assembly)
                if annotations:
                    db.add_all(annotations)
                    db.commit()

                for w in vep_warnings:
                    summary.warnings.append(w)

                analysis_repo.add_event(
                    db, job_id=job_id, stage="ANNOTATING", event_type="STAGE_COMPLETED",
                    message=f"Annotated {len(annotations)} consequences using Ensembl VEP.",
                    details={"annotations_count": len(annotations), "warnings": vep_warnings}
                )

            # 5. Optional ClinVar Evidence Retrieval Stage
            if options.get("retrieve_clinvar_evidence", False):
                analysis_repo.update_status(db, job_id=job_id, status="RUNNING", current_stage="RETRIEVING_EVIDENCE")
                analysis_repo.add_event(
                    db, job_id=job_id, stage="RETRIEVING_EVIDENCE", event_type="STAGE_STARTED",
                    message="Querying NCBI ClinVar for clinical assertions and conflict detection."
                )
                evidence_records, cv_warnings = self.clinvar_client.retrieve_evidence_for_variants(variant_models, assembly=assembly)
                if evidence_records:
                    db.add_all(evidence_records)
                    db.commit()

                for w in cv_warnings:
                    summary.warnings.append(w)

                analysis_repo.add_event(
                    db, job_id=job_id, stage="RETRIEVING_EVIDENCE", event_type="STAGE_COMPLETED",
                    message=f"Retrieved {len(evidence_records)} clinical evidence records from ClinVar.",
                    details={"evidence_count": len(evidence_records), "warnings": cv_warnings}
                )

            # 6. Prioritization Stage (Rule-based candidate ranking)
            analysis_repo.update_status(db, job_id=job_id, status="RUNNING", current_stage="PRIORITIZING")
            analysis_repo.add_event(
                db, job_id=job_id, stage="PRIORITIZING", event_type="STAGE_STARTED",
                message="Evaluating variants using transparent heuristic prioritization matrix."
            )
            db_variants, _ = variant_repo.get_by_analysis(db, analysis_id=job_id, limit=10000)
            prioritization_results = self.prioritizer.prioritize_batch(db_variants)
            if prioritization_results:
                db.add_all(prioritization_results)
                db.commit()

            tier_counts: dict = {}
            for pr in prioritization_results:
                tier_counts[pr.priority_category] = tier_counts.get(pr.priority_category, 0) + 1

            analysis_repo.add_event(
                db, job_id=job_id, stage="PRIORITIZING", event_type="STAGE_COMPLETED",
                message=f"Prioritized {len(prioritization_results)} candidate variants.",
                details={"tier_distribution": tier_counts}
            )

            # 7. Mark COMPLETED (or COMPLETED_WITH_WARNINGS)
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


analysis_service = AnalysisService()

