"""
Modular, decoupled stage executors for the genomic analysis workflow graph.
Each stage handles its own domain logic, bounded retries, and checkpoint recording.
"""
import asyncio
import os
from pathlib import Path
from typing import Any, Dict, List, Optional
from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session, joinedload

from app.ai.explanation_service import ExplanationService, explanation_service
from app.bioinformatics.validator import VCFValidator
from app.bioinformatics.vcf_parser import VCFParser
from app.bioinformatics.vep_client import EnsemblVEPClient, vep_client
from app.core.logging import logger
from app.evidence.clinvar_client import ClinVarClient, clinvar_client
from app.models.annotation import Annotation
from app.models.evidence import EvidenceRecord
from app.models.prioritization import PrioritizationResult
from app.models.variant import Variant
from app.orchestration.state import WorkflowState
from app.prioritization.prioritizer import VariantPrioritizer, prioritizer
from app.repositories.analysis_repository import analysis_repo
from app.repositories.variant_repository import variant_repo


class StageContext:
    """
    Dependency injection container for workflow stage handlers.
    Allows easy unit testing and mocking.
    """
    def __init__(
        self,
        validator: Optional[VCFValidator] = None,
        parser: Optional[VCFParser] = None,
        vep: Optional[EnsemblVEPClient] = None,
        clinvar: Optional[ClinVarClient] = None,
        prioritizer_inst: Optional[VariantPrioritizer] = None,
        explainer: Optional[ExplanationService] = None,
    ):
        self.validator = validator or VCFValidator()
        self.parser = parser or VCFParser()
        self.vep_client = vep or vep_client
        self.clinvar_client = clinvar or clinvar_client
        self.prioritizer = prioritizer_inst or prioritizer
        self.explanation_service = explainer or explanation_service


def check_for_cancellation(state: WorkflowState, db: Session) -> bool:
    """
    Cooperative cancellation check against the database before executing any stage.
    """
    job = analysis_repo.get(db, state.analysis_id)
    if job and job.status == "CANCELLED":
        state.is_cancelled = True
        state.status = "CANCELLED"
        state.current_stage = "CANCELLED"
        logger.info(f"Analysis {state.analysis_id} was cancelled by user; halting stage execution.")
        return True
    return False


def execute_validation_stage(state: WorkflowState, db: Session, context: StageContext) -> None:
    """
    Stage 1: Validates VCF structure, contigs, and assembly alignment.
    """
    stage_name = "VALIDATING"
    if state.is_stage_completed(stage_name):
        logger.info(f"[{state.analysis_id}] {stage_name} already completed in prior checkpoint; skipping.")
        return

    state.record_stage_start(stage_name)
    analysis_repo.update_status(db, job_id=state.analysis_id, status="RUNNING", current_stage=stage_name)
    analysis_repo.add_event(
        db, job_id=state.analysis_id, stage=stage_name, event_type="STAGE_STARTED",
        message="Validating VCF file structure and genome assembly contigs."
    )

    if not os.path.exists(state.file_path):
        err = f"VCF file not found on storage: {state.file_path}"
        state.record_stage_failure(stage_name, err)
        raise FileNotFoundError(err)

    summary = context.validator.validate(state.file_path)
    if not summary.is_valid and summary.accepted_variants_count == 0:
        err = "VCF contains zero valid variant records or corrupted headers."
        state.record_stage_failure(stage_name, err)
        raise ValueError(err)

    for w in summary.warnings:
        state.warnings.append(w)

    metrics = {
        "file_checksum": summary.file_checksum,
        "sample_count": len(summary.sample_names),
        "contigs_declared_count": len(summary.contigs_declared),
        "accepted_variants_count": summary.accepted_variants_count,
    }
    state.record_stage_complete(stage_name, metrics)
    state.validation_status = "COMPLETED"

    analysis_repo.add_event(
        db, job_id=state.analysis_id, stage=stage_name, event_type="STAGE_COMPLETED",
        message=f"Validation passed: {summary.accepted_variants_count} valid records detected.",
        details=metrics
    )


def execute_parsing_stage(state: WorkflowState, db: Session, context: StageContext) -> None:
    """
    Stage 2: Parses genomic variants, expands multiallelic loci, and persists Variant models.
    """
    stage_name = "PARSING"
    if state.is_stage_completed(stage_name):
        logger.info(f"[{state.analysis_id}] {stage_name} already completed in prior checkpoint; skipping.")
        return

    state.record_stage_start(stage_name)
    analysis_repo.update_status(db, job_id=state.analysis_id, status="RUNNING", current_stage=stage_name)
    analysis_repo.add_event(
        db, job_id=state.analysis_id, stage=stage_name, event_type="STAGE_STARTED",
        message="Extracting genomic variants and expanding multiallelic alleles."
    )

    # Check if variants already exist in DB for this analysis (e.g. from prior partial run)
    existing_count = db.scalar(select(func.count(Variant.id)).where(Variant.analysis_id == state.analysis_id)) or 0
    if existing_count > 0:
        logger.info(f"[{state.analysis_id}] {existing_count} variants already exist; skipping re-insertion.")
        state.variants_count = existing_count
        variant_ids = list(db.scalars(select(Variant.id).where(Variant.analysis_id == state.analysis_id)).all())
        state.parsed_variant_ids = variant_ids
        metrics = {
            "variants_inserted": existing_count,
            "multiallelic_sites": 0,
            "resumed": True,
        }
        state.record_stage_complete(stage_name, metrics)
        state.parsing_status = "COMPLETED"
        analysis_repo.add_event(
            db, job_id=state.analysis_id, stage=stage_name, event_type="STAGE_COMPLETED",
            message=f"Verified {existing_count} existing genomic variants.",
            details=metrics
        )
        return

    parsed_variants, summary = context.parser.parse(state.file_path, filename=Path(state.file_path).name)
    variant_models = []
    for pv in parsed_variants:
        v = Variant(
            analysis_id=state.analysis_id,
            chromosome=pv.chromosome,
            position=pv.position,
            reference_allele=pv.reference_allele,
            alternate_allele=pv.alternate_allele,
            variant_identifier=pv.variant_id,
            variant_type=pv.variant_type.value if hasattr(pv.variant_type, "value") else str(pv.variant_type),
            quality=pv.quality,
            filter_status=pv.filter_status,
            genotype_json={"gt": pv.genotype} if pv.genotype else None,
            info_json=pv.info_fields,
            allele_index=pv.allele_index,
            is_multiallelic=pv.is_multiallelic,
        )
        variant_models.append(v)

    inserted = variant_repo.bulk_create(db, variant_models)
    state.variants_count = inserted
    state.parsed_variant_ids = [v.id for v in variant_models]

    metrics = {
        "variants_inserted": inserted,
        "multiallelic_sites": sum(1 for v in variant_models if v.is_multiallelic),
    }
    state.record_stage_complete(stage_name, metrics)
    state.parsing_status = "COMPLETED"

    analysis_repo.add_event(
        db, job_id=state.analysis_id, stage=stage_name, event_type="STAGE_COMPLETED",
        message=f"Parsed and persisted {inserted} genomic variants.",
        details=metrics
    )


def execute_annotation_stage(state: WorkflowState, db: Session, context: StageContext) -> None:
    """
    Stage 3: Annotates variants using Ensembl VEP REST API with bounded exponential backoff.
    """
    stage_name = "ANNOTATING"
    if not state.options.get("annotate_with_vep", False):
        state.record_stage_skipped(stage_name, "VEP consequence annotation disabled by user configuration.")
        state.annotation_status = "SKIPPED"
        return

    if state.is_stage_completed(stage_name):
        logger.info(f"[{state.analysis_id}] {stage_name} already completed in prior checkpoint; skipping.")
        return

    state.record_stage_start(stage_name)
    analysis_repo.update_status(db, job_id=state.analysis_id, status="RUNNING", current_stage=stage_name)
    analysis_repo.add_event(
        db, job_id=state.analysis_id, stage=stage_name, event_type="STAGE_STARTED",
        message="Querying Ensembl VEP REST API for transcript consequence annotations."
    )

    variants = list(db.scalars(select(Variant).where(Variant.analysis_id == state.analysis_id)).all())
    variant_ids = [v.id for v in variants]
    if variant_ids:
        db.execute(delete(Annotation).where(Annotation.variant_id.in_(variant_ids)))
        db.commit()

    annotations, vep_warnings = context.vep_client.annotate_variants(variants, assembly=state.genome_assembly)

    if annotations:
        db.add_all(annotations)
        db.commit()

    for w in vep_warnings:
        state.warnings.append(w)

    state.annotated_count = len(annotations)
    metrics = {
        "annotations_created": len(annotations),
        "vep_warnings_count": len(vep_warnings),
    }
    state.record_stage_complete(stage_name, metrics)
    state.annotation_status = "COMPLETED"

    analysis_repo.add_event(
        db, job_id=state.analysis_id, stage=stage_name, event_type="STAGE_COMPLETED",
        message=f"Annotated {len(annotations)} consequences using Ensembl VEP.",
        details=metrics
    )


def execute_evidence_stage(state: WorkflowState, db: Session, context: StageContext) -> None:
    """
    Stage 4: Queries NCBI ClinVar Entrez E-Utilities for clinical interpretations and submitter conflicts.
    """
    stage_name = "RETRIEVING_EVIDENCE"
    if not state.options.get("retrieve_clinvar_evidence", False):
        state.record_stage_skipped(stage_name, "ClinVar evidence retrieval disabled by user configuration.")
        state.evidence_status = "SKIPPED"
        return

    if state.is_stage_completed(stage_name):
        logger.info(f"[{state.analysis_id}] {stage_name} already completed in prior checkpoint; skipping.")
        return

    state.record_stage_start(stage_name)
    analysis_repo.update_status(db, job_id=state.analysis_id, status="RUNNING", current_stage=stage_name)
    analysis_repo.add_event(
        db, job_id=state.analysis_id, stage=stage_name, event_type="STAGE_STARTED",
        message="Querying NCBI ClinVar Entrez E-Utilities for public clinical assertions."
    )

    variants = list(db.scalars(select(Variant).where(Variant.analysis_id == state.analysis_id)).all())
    variant_ids = [v.id for v in variants]
    if variant_ids:
        db.execute(delete(EvidenceRecord).where(EvidenceRecord.variant_id.in_(variant_ids)))
        db.commit()

    evidence_records, cv_warnings = context.clinvar_client.retrieve_evidence_for_variants(
        variants, assembly=state.genome_assembly
    )

    if evidence_records:
        db.add_all(evidence_records)
        db.commit()

    for w in cv_warnings:
        state.warnings.append(w)

    state.evidence_count = len(evidence_records)
    metrics = {
        "evidence_records_count": len(evidence_records),
        "conflicting_assertions_count": sum(1 for e in evidence_records if e.has_conflicts),
    }
    state.record_stage_complete(stage_name, metrics)
    state.evidence_status = "COMPLETED"

    analysis_repo.add_event(
        db, job_id=state.analysis_id, stage=stage_name, event_type="STAGE_COMPLETED",
        message=f"Retrieved {len(evidence_records)} ClinVar evidence records.",
        details=metrics
    )


def execute_prioritization_stage(state: WorkflowState, db: Session, context: StageContext) -> None:
    """
    Stage 5: Applies versioned heuristic rule matrix to categorize candidates into Tiers 1-4.
    """
    stage_name = "PRIORITIZING"
    if state.is_stage_completed(stage_name):
        logger.info(f"[{state.analysis_id}] {stage_name} already completed in prior checkpoint; skipping.")
        return

    state.record_stage_start(stage_name)
    analysis_repo.update_status(db, job_id=state.analysis_id, status="RUNNING", current_stage=stage_name)
    analysis_repo.add_event(
        db, job_id=state.analysis_id, stage=stage_name, event_type="STAGE_STARTED",
        message="Applying rule-based heuristic matrix to calculate variant candidate priority scores."
    )

    stmt = (
        select(Variant)
        .where(Variant.analysis_id == state.analysis_id)
        .options(
            joinedload(Variant.annotations),
            joinedload(Variant.evidence_records)
        )
    )
    variants = list(db.scalars(stmt).unique().all())
    variant_ids = [v.id for v in variants]
    if variant_ids:
        db.execute(delete(PrioritizationResult).where(PrioritizationResult.variant_id.in_(variant_ids)))
        db.commit()

    prio_results = context.prioritizer.prioritize_batch(variants)

    if prio_results:
        db.add_all(prio_results)
        db.commit()

    tier_dist: Dict[str, int] = {}
    for pr in prio_results:
        tier_dist[pr.priority_category] = tier_dist.get(pr.priority_category, 0) + 1

    state.prioritized_count = len(prio_results)
    metrics = {
        "prioritized_count": len(prio_results),
        "tier_distribution": tier_dist,
    }
    state.record_stage_complete(stage_name, metrics)
    state.prioritization_status = "COMPLETED"

    analysis_repo.add_event(
        db, job_id=state.analysis_id, stage=stage_name, event_type="STAGE_COMPLETED",
        message=f"Prioritized {len(prio_results)} candidate variants into tiers.",
        details=metrics
    )


def execute_explanation_stage(state: WorkflowState, db: Session, context: StageContext) -> None:
    """
    Stage 6: (Optional) Generates grounded AI explanations for top candidate variants.
    Fail-safe: failure in LLM does not abort earlier bioinformatics results.
    """
    stage_name = "GENERATING_EXPLANATIONS"
    if not state.options.get("generate_ai_explanations", False):
        state.record_stage_skipped(stage_name, "AI explanation generation disabled by user configuration.")
        state.explanation_status = "SKIPPED"
        return

    if state.is_stage_completed(stage_name):
        logger.info(f"[{state.analysis_id}] {stage_name} already completed in prior checkpoint; skipping.")
        return

    state.record_stage_start(stage_name)
    analysis_repo.update_status(db, job_id=state.analysis_id, status="RUNNING", current_stage=stage_name)
    analysis_repo.add_event(
        db, job_id=state.analysis_id, stage=stage_name, event_type="STAGE_STARTED",
        message="Synthesizing grounded AI explanations for candidate variants."
    )

    try:
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                import concurrent.futures
                with concurrent.futures.ThreadPoolExecutor() as executor:
                    future = executor.submit(
                        asyncio.run,
                        context.explanation_service.explain_analysis_candidates(
                            db=db, analysis_id=state.analysis_id, limit=10, genome_assembly=state.genome_assembly
                        )
                    )
                    explanations = future.result()
            else:
                explanations = loop.run_until_complete(
                    context.explanation_service.explain_analysis_candidates(
                        db=db, analysis_id=state.analysis_id, limit=10, genome_assembly=state.genome_assembly
                    )
                )
        except RuntimeError:
            explanations = asyncio.run(
                context.explanation_service.explain_analysis_candidates(
                    db=db, analysis_id=state.analysis_id, limit=10, genome_assembly=state.genome_assembly
                )
            )

        state.explanations_count = len(explanations)
        metrics = {"explanations_count": len(explanations)}
        state.record_stage_complete(stage_name, metrics)
        state.explanation_status = "COMPLETED"

        analysis_repo.add_event(
            db, job_id=state.analysis_id, stage=stage_name, event_type="STAGE_COMPLETED",
            message=f"Generated {len(explanations)} evidence-grounded AI explanations.",
            details=metrics
        )
    except Exception as e:
        logger.warning(f"AI explanation skipped with non-fatal warning: {e}")
        state.warnings.append(f"AI explanation partially skipped: {str(e)}")
        state.record_stage_skipped(stage_name, f"Non-fatal error: {str(e)}")
        state.explanation_status = "FAILED_OPTIONAL"
        analysis_repo.add_event(
            db, job_id=state.analysis_id, stage=stage_name, event_type="STAGE_WARNING",
            message=f"AI explanation generation skipped: {str(e)}"
        )


def execute_finalize_stage(state: WorkflowState, db: Session, context: StageContext) -> None:
    """
    Stage 7: Finalizes pipeline execution, determines final completion status, and records audit close.
    """
    stage_name = "FINALIZE"
    final_status = "COMPLETED_WITH_WARNINGS" if state.warnings else "COMPLETED"
    state.status = final_status
    state.current_stage = "FINISHED"

    analysis_repo.update_status(db, job_id=state.analysis_id, status=final_status, current_stage="FINISHED")
    analysis_repo.add_event(
        db, job_id=state.analysis_id, stage="FINISHED", event_type="JOB_COMPLETED",
        message=f"Genomic analysis completed successfully with status: {final_status}.",
        details={
            "variants_total": state.variants_count,
            "annotations_total": state.annotated_count,
            "evidence_total": state.evidence_count,
            "prioritized_total": state.prioritized_count,
            "warnings_count": len(state.warnings),
        }
    )
