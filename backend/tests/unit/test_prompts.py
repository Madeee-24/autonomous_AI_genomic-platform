"""
Unit tests for AI explanation prompt formatting and data sanitization.
"""
from app.ai.prompts import PROMPT_VERSION, format_evidence_payload, build_variant_explanation_prompt


def test_format_evidence_payload_sanitization():
    payload = format_evidence_payload(
        chromosome="chr17",
        position=7674220,
        reference_allele="C",
        alternate_allele="T",
        genome_assembly="GRCh38",
        variant_identifier="rs121913343",
        annotations=[{
            "gene_symbol": "TP53",
            "consequence": "missense_variant",
            "impact": "HIGH"
        }],
        evidence_records=[{
            "source_name": "ClinVar",
            "source_accession": "VCV000012374.5",
            "interpretation": "Pathogenic",
            "review_status": "criteria provided, multiple submitters, no conflicts",
            "has_conflicts": False
        }],
        prioritization={
            "priority_category": "TIER_1_CRITICAL",
            "score": 85.0
        }
    )

    # Check that structure is clean
    assert payload["variant"]["coordinate"] == "chr17:7674220"
    assert payload["variant"]["genome_assembly"] == "GRCh38"
    assert payload["variant"]["dbsnp_id"] == "rs121913343"
    assert len(payload["annotations"]) == 1
    assert payload["annotations"][0]["gene_symbol"] == "TP53"
    assert len(payload["clinical_evidence"]) == 1
    assert payload["clinical_evidence"][0]["interpretation"] == "Pathogenic"
    assert payload["prioritization_matrix"]["score"] == 85.0


def test_build_variant_explanation_prompt():
    prompt = build_variant_explanation_prompt(
        chromosome="chr7",
        position=117559590,
        reference_allele="ATCT",
        alternate_allele="A",
        genome_assembly="GRCh38",
        variant_type="INDEL"
    )

    assert "GENOMIC VARIANT RECORD CONTEXT:" in prompt
    assert "chr7:117559590" in prompt
    assert "ATCT>A" in prompt
    assert "GRCh38" in prompt
    assert PROMPT_VERSION == "v1.0"

