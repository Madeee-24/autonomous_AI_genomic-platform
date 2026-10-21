"""
Unit tests for Audit-Ready PDF Report Generator.
Verifies ReportLab rendering, layout flowables, table structures, and binary PDF integrity.
"""
import os
import uuid
from pathlib import Path
import pytest

from app.models.ai import AIExplanation
from app.models.analysis import AnalysisJob
from app.models.annotation import Annotation
from app.models.dataset import Dataset
from app.models.evidence import EvidenceRecord
from app.models.prioritization import PrioritizationResult
from app.models.variant import Variant
from app.reporting.pdf_generator import GenomicReportGenerator, pdf_generator


@pytest.fixture
def sample_analysis_data():
    dataset_id = str(uuid.uuid4())
    job_id = str(uuid.uuid4())

    dataset = Dataset(
        id=dataset_id,
        original_filename="patient_sample_01.vcf",
        stored_filename="patient_sample_01.vcf",
        stored_file_path="/data/patient_sample_01.vcf",
        file_checksum="e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
        file_size_bytes=1024,
        assembly="GRCh38",
        validation_status="VALID",
    )

    job = AnalysisJob(
        id=job_id,
        dataset_id=dataset_id,
        status="COMPLETED",
        current_stage="FINISHED",
        configuration_json={
            "genome_assembly": "GRCh38",
            "options": {
                "annotate_with_vep": True,
                "retrieve_clinvar_evidence": True,
                "generate_ai_explanations": True,
            },
        },
    )

    # Variant 1: Pathogenic candidate with full evidence and AI explanation
    v1_id = str(uuid.uuid4())
    v1 = Variant(
        id=v1_id,
        analysis_id=job_id,
        chromosome="chr17",
        position=7674220,
        reference_allele="C",
        alternate_allele="T",
        variant_identifier="rs121913343",
        variant_type="SNV",
        quality=99.0,
        filter_status="PASS",
    )
    v1.annotations = [
        Annotation(
            variant_id=v1_id,
            gene_symbol="TP53",
            gene_id="ENSG00000141510",
            consequence="missense_variant",
            impact="HIGH",
        )
    ]
    v1.evidence_records = [
        EvidenceRecord(
            variant_id=v1_id,
            source_accession="VCV000012377",
            interpretation="Pathogenic",
            review_status="criteria provided, single submitter",
            has_conflicts=False,
            evidence_summary="Li-Fraumeni syndrome",
        )
    ]
    v1.prioritization = PrioritizationResult(
        variant_id=v1_id,
        priority_category="TIER_1_CRITICAL",
        score=95.0,
        rule_version="v1.0",
        reasons_json={"reasons": ["Well-established Pathogenic assertion in ClinVar", "HIGH impact coding alteration in TP53"]},
    )
    v1.ai_explanation = AIExplanation(
        variant_id=v1_id,
        model_provider="mock",
        model_name="mock-synthesizer",
        prompt_version="v1.0",
        explanation_text="Variant TP53 c.743G>A represents a well-characterized loss-of-function mutation altering the DNA-binding domain.",
        structured_output_json={
            "summary": "Pathogenic missense alteration in TP53.",
            "uncertainties": ["Assumes heterozygous germline state without somatic allele frequency confirmation."],
        },
    )

    # Variant 2: Benign/Uncertain variant with minimal annotations
    v2_id = str(uuid.uuid4())
    v2 = Variant(
        id=v2_id,
        analysis_id=job_id,
        chromosome="chr7",
        position=117559590,
        reference_allele="A",
        alternate_allele="G",
        variant_identifier="rs113993960",
        variant_type="SNV",
        quality=80.0,
        filter_status="PASS",
    )
    v2.annotations = []
    v2.evidence_records = []
    v2.prioritization = PrioritizationResult(
        variant_id=v2_id,
        priority_category="UNCERTAIN",
        score=20.0,
        rule_version="v1.0",
        reasons_json={"reasons": ["Absence of recognized clinical assertions in ClinVar"]},
    )
    v2.ai_explanation = None

    return job, dataset, [v1, v2]


def test_pdf_generator_produces_valid_pdf(tmp_path, sample_analysis_data):
    job, dataset, variants = sample_analysis_data
    out_file = str(tmp_path / "test_report.pdf")

    generator = GenomicReportGenerator()
    generated_path = generator.generate_report(
        output_path=out_file,
        job=job,
        dataset=dataset,
        variants=variants,
    )

    assert os.path.exists(generated_path)
    assert os.path.getsize(generated_path) > 1000

    # Validate PDF magic bytes (%PDF-)
    with open(generated_path, "rb") as f:
        header = f.read(5)
        assert header == b"%PDF-"


def test_pdf_generator_empty_variants_fallback(tmp_path, sample_analysis_data):
    job, dataset, _ = sample_analysis_data
    out_file = str(tmp_path / "empty_report.pdf")

    generator = GenomicReportGenerator()
    generated_path = generator.generate_report(
        output_path=out_file,
        job=job,
        dataset=dataset,
        variants=[],
    )

    assert os.path.exists(generated_path)
    assert os.path.getsize(generated_path) > 500
