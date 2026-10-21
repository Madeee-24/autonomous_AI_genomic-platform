"""
Unit tests for ExplanationService execution, schema validation, and persistence.
"""
import uuid
import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.ai.explanation_service import ExplanationService
from app.ai.llm_client import MockLLMClient
from app.db.base import Base
from app.models.ai import AIExplanation
from app.models.annotation import Annotation
from app.models.evidence import EvidenceRecord
from app.models.prioritization import PrioritizationResult
from app.models.variant import Variant


@pytest.fixture
def in_memory_db():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    db = Session()
    try:
        yield db
    finally:
        db.close()
        Base.metadata.drop_all(bind=engine)


@pytest.mark.asyncio
async def test_explanation_service_generates_and_persists(in_memory_db):
    service = ExplanationService(client=MockLLMClient(model_name="mock-model"))

    # Create dummy variant in DB
    variant_id = str(uuid.uuid4())
    job_id = str(uuid.uuid4())
    variant = Variant(
        id=variant_id,
        analysis_id=job_id,
        chromosome="chr17",
        position=7674220,
        reference_allele="C",
        alternate_allele="T",
        variant_identifier="rs121913343",
    )
    in_memory_db.add(variant)

    ann = Annotation(
        variant_id=variant_id,
        gene_symbol="TP53",
        gene_id="ENSG00000141510",
        consequence="missense_variant",
        impact="HIGH",
    )
    ev = EvidenceRecord(
        variant_id=variant_id,
        source_name="ClinVar",
        source_accession="VCV000012374.5",
        interpretation="Pathogenic",
        review_status="criteria provided, multiple submitters, no conflicts",
        has_conflicts=False,
    )
    prio = PrioritizationResult(
        variant_id=variant_id,
        priority_category="TIER_1_CRITICAL",
        score=85.0,
        rule_version="v1.0",
    )
    in_memory_db.add_all([ann, ev, prio])
    in_memory_db.commit()

    # Generate explanation
    result = await service.generate_variant_explanation(
        db=in_memory_db,
        variant=variant,
        genome_assembly="GRCh38",
        persist=True,
    )

    assert result.is_valid is True
    assert result.parsed_output is not None
    assert "TP53" in result.parsed_output.summary
    assert "Pathogenic" in result.parsed_output.summary

    # Verify persistence in database
    saved_exp = in_memory_db.scalar(select(AIExplanation).where(AIExplanation.variant_id == variant_id))
    assert saved_exp is not None
    assert saved_exp.validation_status == "VALID"
    assert saved_exp.model_provider == "mock"
    assert "TP53" in saved_exp.explanation_text
    assert saved_exp.structured_output_json is not None
    assert "confidence_assessment" in saved_exp.structured_output_json


@pytest.mark.asyncio
async def test_explanation_service_missing_evidence_neutrality(in_memory_db):
    service = ExplanationService(client=MockLLMClient(model_name="mock-model"))

    # Variant with NO ClinVar evidence
    variant_id = str(uuid.uuid4())
    job_id = str(uuid.uuid4())
    variant = Variant(
        id=variant_id,
        analysis_id=job_id,
        chromosome="chr1",
        position=10000,
        reference_allele="A",
        alternate_allele="G",
    )
    in_memory_db.add(variant)
    ann = Annotation(
        variant_id=variant_id,
        gene_symbol="TESTG",
        consequence="synonymous_variant",
        impact="LOW",
    )
    in_memory_db.add(ann)
    in_memory_db.commit()

    result = await service.generate_variant_explanation(
        db=in_memory_db,
        variant=variant,
        genome_assembly="GRCh38",
        persist=True,
    )

    assert result.is_valid is True
    assert "no matching assertions are recorded in NCBI ClinVar" in result.parsed_output.summary.lower() or "currently" in result.parsed_output.summary.lower()
    assert len(result.parsed_output.uncertainties) > 0
