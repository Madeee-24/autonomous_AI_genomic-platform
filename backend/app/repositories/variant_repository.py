"""
Variant repository for bulk persisting and querying parsed variants and their annotations.
"""
from typing import List, Optional, Tuple
from sqlalchemy import func, select
from sqlalchemy.orm import Session, joinedload

from app.models.annotation import Annotation
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
        skip: int = 0,
        limit: int = 50
    ) -> Tuple[List[Variant], int]:
        """
        Retrieves paginated variants for an analysis with optional chromosome filter.
        Includes eager loading of annotations and clinical evidence.
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

        count_stmt = select(func.count(Variant.id)).where(Variant.analysis_id == analysis_id)

        if chromosome:
            stmt = stmt.where(Variant.chromosome == chromosome)
            count_stmt = count_stmt.where(Variant.chromosome == chromosome)

        total = db.scalar(count_stmt) or 0
        variants = list(db.scalars(stmt.offset(skip).limit(limit)).unique().all())

        return variants, total


variant_repo = VariantRepository()
