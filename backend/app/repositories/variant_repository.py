"""
Variant repository for bulk persisting and querying parsed variants, annotations, evidence, and prioritization.
"""
from collections import Counter
from typing import Any, Dict, List, Optional, Tuple
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session, joinedload

from app.models.analysis import AnalysisJob
from app.models.annotation import Annotation
from app.models.dataset import Dataset
from app.models.evidence import EvidenceRecord
from app.models.prioritization import PrioritizationResult
from app.models.variant import Variant
from app.repositories.base import BaseRepository


class VariantRepository(BaseRepository[Variant]):
    def __init__(self):
        super().__init__(Variant)

    def bulk_create(self, db: Session, variants: List[Variant]) -> int:
        """
        Efficiently inserts large batches of parsed variants.
        """
        db.add_all(variants)
        db.commit()
        return len(variants)

    def get_by_analysis(
        self,
        db: Session,
        analysis_id: str,
        chromosome: Optional[str] = None,
        gene: Optional[str] = None,
        consequence: Optional[str] = None,
        priority_category: Optional[str] = None,
        has_conflicts: Optional[bool] = None,
        search: Optional[str] = None,
        skip: int = 0,
        limit: int = 50,
    ) -> Tuple[List[Variant], int]:
        """
        Retrieves paginated variants for an analysis with optional filters.
        Includes eager loading of annotations, evidence, and prioritization.
        """
        stmt = (
            select(Variant)
            .where(Variant.analysis_id == analysis_id)
            .options(
                joinedload(Variant.annotations),
                joinedload(Variant.evidence_records),
                joinedload(Variant.prioritization)
            )
        )
        count_stmt = select(func.count(func.distinct(Variant.id))).where(Variant.analysis_id == analysis_id)

        # Filters
        if chromosome:
            norm_chr = chromosome if chromosome.startswith("chr") else f"chr{chromosome}"
            # Support both chr-prefixed and un-prefixed in db
            chr_filter = or_(Variant.chromosome == chromosome, Variant.chromosome == norm_chr, Variant.chromosome == chromosome.replace("chr", ""))
            stmt = stmt.where(chr_filter)
            count_stmt = count_stmt.where(chr_filter)

        if gene:
            gene_filter = Variant.id.in_(
                select(Annotation.variant_id).where(
                    or_(
                        Annotation.gene_symbol.ilike(f"%{gene}%"),
                        Annotation.gene_id.ilike(f"%{gene}%")
                    )
                )
            )
            stmt = stmt.where(gene_filter)
            count_stmt = count_stmt.where(gene_filter)

        if consequence:
            csq_filter = Variant.id.in_(
                select(Annotation.variant_id).where(Annotation.consequence.ilike(f"%{consequence}%"))
            )
            stmt = stmt.where(csq_filter)
            count_stmt = count_stmt.where(csq_filter)

        if priority_category:
            prio_filter = Variant.id.in_(
                select(PrioritizationResult.variant_id).where(
                    PrioritizationResult.priority_category == priority_category
                )
            )
            stmt = stmt.where(prio_filter)
            count_stmt = count_stmt.where(prio_filter)

        if has_conflicts is not None:
            conf_filter = Variant.id.in_(
                select(EvidenceRecord.variant_id).where(EvidenceRecord.has_conflicts == has_conflicts)
            )
            stmt = stmt.where(conf_filter)
            count_stmt = count_stmt.where(conf_filter)

        if search:
            search_term = f"%{search}%"
            gene_subquery = select(Annotation.variant_id).where(Annotation.gene_symbol.ilike(search_term))
            search_filter = or_(
                Variant.variant_identifier.ilike(search_term),
                Variant.chromosome.ilike(search_term),
                Variant.id.in_(gene_subquery)
            )
            stmt = stmt.where(search_filter)
            count_stmt = count_stmt.where(search_filter)

        # Count total matching distinct variants
        total = db.scalar(count_stmt) or 0

        # Sort predictably by chromosome, position, allele_index
        stmt = stmt.order_by(Variant.chromosome, Variant.position, Variant.allele_index)
        variants = list(db.scalars(stmt.offset(skip).limit(limit)).unique().all())

        return variants, total

    def get_variant_detail(self, db: Session, variant_id: str) -> Optional[Variant]:
        """
        Retrieves a single variant with all joined annotations, evidence, and prioritization.
        """
        stmt = (
            select(Variant)
            .where(Variant.id == variant_id)
            .options(
                joinedload(Variant.annotations),
                joinedload(Variant.evidence_records),
                joinedload(Variant.prioritization)
            )
        )
        return db.scalars(stmt).unique().first()

    def get_statistics(self, db: Session, analysis_id: str) -> Dict[str, Any]:
        """
        Computes aggregated summary statistics for an analysis job.
        """
        variants_stmt = (
            select(Variant)
            .where(Variant.analysis_id == analysis_id)
            .options(
                joinedload(Variant.annotations),
                joinedload(Variant.evidence_records),
                joinedload(Variant.prioritization)
            )
        )
        variants = list(db.scalars(variants_stmt).unique().all())
        total = len(variants)

        tier_counter: Counter = Counter()
        consequence_counter: Counter = Counter()
        impact_counter: Counter = Counter()
        clinvar_counter: Counter = Counter()

        annotated_count = 0
        evidence_count = 0
        prioritized_count = 0

        for v in variants:
            if v.annotations:
                annotated_count += 1
                for ann in v.annotations:
                    if ann.consequence:
                        consequence_counter[ann.consequence] += 1
                    if ann.impact:
                        impact_counter[ann.impact] += 1

            if v.evidence_records:
                evidence_count += 1
                for ev in v.evidence_records:
                    if ev.interpretation:
                        clinvar_counter[ev.interpretation] += 1

            if v.prioritization:
                prioritized_count += 1
                tier_counter[v.prioritization.priority_category] += 1
            else:
                tier_counter["UNCERTAIN"] += 1

        ann_cov = round((annotated_count / total * 100), 1) if total > 0 else 0.0
        ev_cov = round((evidence_count / total * 100), 1) if total > 0 else 0.0

        return {
            "analysis_id": analysis_id,
            "total_variants": total,
            "annotated_variants": annotated_count,
            "evidence_variants": evidence_count,
            "prioritized_variants": prioritized_count,
            "annotation_coverage_pct": ann_cov,
            "evidence_coverage_pct": ev_cov,
            "tier_counts": dict(tier_counter),
            "consequence_counts": dict(consequence_counter),
            "impact_counts": dict(impact_counter),
            "clinvar_counts": dict(clinvar_counter),
        }

    def get_dashboard_summary(self, db: Session) -> Dict[str, Any]:
        """
        Aggregates system-wide counts for datasets, jobs, variants, and tier breakdown.
        """
        from app.services.dataset_service import dataset_service
        total_datasets = max(db.scalar(select(func.count(Dataset.id))) or 0, len(dataset_service._registry))
        total_analyses = db.scalar(select(func.count(AnalysisJob.id))) or 0
        running_analyses = db.scalar(
            select(func.count(AnalysisJob.id)).where(AnalysisJob.status == "RUNNING")
        ) or 0
        completed_analyses = db.scalar(
            select(func.count(AnalysisJob.id)).where(AnalysisJob.status == "COMPLETED")
        ) or 0
        failed_analyses = db.scalar(
            select(func.count(AnalysisJob.id)).where(AnalysisJob.status == "FAILED")
        ) or 0
        total_variants = db.scalar(select(func.count(Variant.id))) or 0

        # Prioritization tier distribution across all completed jobs
        tier_counts = db.execute(
            select(PrioritizationResult.priority_category, func.count(PrioritizationResult.id))
            .group_by(PrioritizationResult.priority_category)
        ).all()
        tier_dist = {cat: count for cat, count in tier_counts}

        return {
            "total_datasets": total_datasets,
            "total_analyses": total_analyses,
            "running_analyses": running_analyses,
            "completed_analyses": completed_analyses,
            "failed_analyses": failed_analyses,
            "total_variants_processed": total_variants,
            "average_annotation_coverage_pct": 100.0 if total_variants > 0 else 0.0,
            "average_evidence_coverage_pct": 100.0 if total_variants > 0 else 0.0,
            "tier_distribution": tier_dist,
        }


variant_repo = VariantRepository()
