"""
Unit tests for the transparent rule-based variant prioritization engine.
"""
import pytest

from app.models.annotation import Annotation
from app.models.evidence import EvidenceRecord
from app.models.variant import Variant
from app.prioritization.prioritizer import VariantPrioritizer
from app.prioritization.rules import PriorityCategory, RULE_VERSION


@pytest.fixture
def prioritizer():
    return VariantPrioritizer()


def test_prioritize_pathogenic_high_impact(prioritizer):
    variant = Variant(
        chromosome="chr17",
        position=7675088,
        reference_allele="C",
        alternate_allele="T",
        variant_identifier="rs28934578",
        filter_status="PASS"
    )
    annotation = Annotation(
        variant_id=variant.id,
        gene_symbol="TP53",
        consequence="stop_gained",
        impact="HIGH"
    )
    evidence = EvidenceRecord(
        variant_id=variant.id,
        source_name="ClinVar",
        source_accession="VCV000012374",
        interpretation="Pathogenic",
        review_status="reviewed by expert panel",
        has_conflicts=False
    )

    evaluation = prioritizer.evaluate_variant(
        variant,
        annotations=[annotation],
        evidence_records=[evidence]
    )

    # 10 (PASS) + 40 (HIGH) + 45 (Pathogenic) + 5 (Expert Panel) = 100.0
    assert evaluation.score == 100.0
    assert evaluation.priority_category == PriorityCategory.TIER_1_CRITICAL
    assert evaluation.has_conflicting_evidence is False
    assert len(evaluation.triggered_rules) == 4


def test_prioritize_likely_pathogenic_moderate_impact(prioritizer):
    variant = Variant(
        chromosome="chr13",
        position=32338763,
        reference_allele="G",
        alternate_allele="A",
        variant_identifier="rs80359550",
        filter_status="PASS"
    )
    annotation = Annotation(
        variant_id=variant.id,
        gene_symbol="BRCA2",
        consequence="missense_variant",
        impact="MODERATE"
    )
    evidence = EvidenceRecord(
        variant_id=variant.id,
        source_name="ClinVar",
        interpretation="Likely pathogenic",
        review_status="criteria provided, single submitter",
        has_conflicts=False
    )

    evaluation = prioritizer.evaluate_variant(
        variant,
        annotations=[annotation],
        evidence_records=[evidence]
    )

    # 10 (PASS) + 25 (MODERATE) + 35 (Likely pathogenic) + 1 (Single submitter) = 71.0
    assert evaluation.score == 71.0
    assert evaluation.priority_category == PriorityCategory.TIER_2_HIGH


def test_prioritize_vus_missense(prioritizer):
    variant = Variant(
        chromosome="chr1",
        position=100000,
        reference_allele="C",
        alternate_allele="T",
        filter_status="PASS"
    )
    annotation = Annotation(
        variant_id=variant.id,
        gene_symbol="GENE1",
        consequence="missense_variant",
        impact="MODERATE"
    )
    evidence = EvidenceRecord(
        variant_id=variant.id,
        source_name="ClinVar",
        interpretation="Uncertain significance",
        review_status="criteria provided, single submitter",
        has_conflicts=False
    )

    evaluation = prioritizer.evaluate_variant(
        variant,
        annotations=[annotation],
        evidence_records=[evidence]
    )

    # 10 (PASS) + 25 (MODERATE) + 15 (VUS) + 1 (Single submitter) = 51.0
    assert evaluation.score == 51.0
    assert evaluation.priority_category == PriorityCategory.TIER_3_MODERATE


def test_prioritize_benign(prioritizer):
    variant = Variant(
        chromosome="chr1",
        position=69091,
        reference_allele="A",
        alternate_allele="G",
        filter_status="PASS"
    )
    annotation = Annotation(
        variant_id=variant.id,
        gene_symbol="OR4F5",
        consequence="synonymous_variant",
        impact="LOW"
    )
    evidence = EvidenceRecord(
        variant_id=variant.id,
        source_name="ClinVar",
        interpretation="Benign",
        review_status="criteria provided, multiple submitters, no conflicts",
        has_conflicts=False
    )

    evaluation = prioritizer.evaluate_variant(
        variant,
        annotations=[annotation],
        evidence_records=[evidence]
    )

    # 10 (PASS) + 10 (LOW) - 30 (Benign) + 3 (Multiple submitters) = -7 -> clamped to 0.0
    assert evaluation.score == 0.0
    assert evaluation.priority_category == PriorityCategory.TIER_4_LOW


def test_prioritize_conflicting_evidence(prioritizer):
    variant = Variant(
        chromosome="chr13",
        position=32338763,
        reference_allele="G",
        alternate_allele="A",
        filter_status="PASS"
    )
    evidence = EvidenceRecord(
        variant_id=variant.id,
        source_name="ClinVar",
        interpretation="Conflicting classifications of pathogenicity",
        has_conflicts=True
    )

    evaluation = prioritizer.evaluate_variant(
        variant,
        annotations=[],
        evidence_records=[evidence]
    )

    assert evaluation.priority_category == PriorityCategory.UNCERTAIN
    assert evaluation.has_conflicting_evidence is True
    assert any("conflicting" in limit.lower() for limit in evaluation.limitations)


def test_prioritize_missing_evidence_neutrality(prioritizer):
    variant = Variant(
        chromosome="chr1",
        position=50000,
        reference_allele="A",
        alternate_allele="C",
        filter_status="PASS"
    )

    evaluation = prioritizer.evaluate_variant(
        variant,
        annotations=[],
        evidence_records=[]
    )

    # 10 (PASS) + 0 (VEP absent) + 0 (ClinVar absent) = 10.0
    assert evaluation.score == 10.0
    assert evaluation.priority_category == PriorityCategory.UNCERTAIN
    assert any("unasserted" in limit.lower() for limit in evaluation.limitations)
    assert any("functional consequence" in limit.lower() for limit in evaluation.limitations)


def test_prioritize_to_model(prioritizer):
    variant = Variant(
        chromosome="chr7",
        position=117559590,
        reference_allele="ATCT",
        alternate_allele="A",
        filter_status="PASS"
    )
    annotation = Annotation(
        variant_id=variant.id,
        gene_symbol="CFTR",
        consequence="frameshift_variant",
        impact="HIGH"
    )

    model_result = prioritizer.prioritize_variant_to_model(
        variant,
        annotations=[annotation],
        evidence_records=[]
    )

    assert model_result.variant_id == variant.id
    assert model_result.rule_version == RULE_VERSION
    assert model_result.score == 50.0  # 10 (PASS) + 40 (HIGH)
    assert model_result.priority_category == PriorityCategory.TIER_2_HIGH.value
    assert "scoring_breakdown" in model_result.reasons_json
    assert "data_limitations" in model_result.limitations_json

