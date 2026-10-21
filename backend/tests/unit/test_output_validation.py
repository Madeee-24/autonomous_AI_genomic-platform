"""
Unit tests for AI explanation output validation schemas and ethical guardrails.
"""
import pytest
from pydantic import ValidationError

from app.ai.output_validation import VariantExplanationOutput


def test_valid_explanation_output():
    data = {
        "summary": "Variant chr17:7674220 C>T in TP53 is recorded in NCBI ClinVar as Pathogenic.",
        "variant_context": "The mutation causes a missense consequence with high functional impact in the DNA-binding domain.",
        "supporting_evidence": [
            "ClinVar record VCV000012374 asserts Pathogenic review status with 2 stars.",
            "VEP predicts high impact missense alteration."
        ],
        "conflicting_evidence": ["No conflicting submitter classifications reported."],
        "uncertainties": ["Absence of patient-specific functional cellular assays."],
        "missing_information": ["Population allele frequency was not queried."],
        "source_references": ["NCBI ClinVar: VCV000012374"],
        "limitations": ["Academic research-support analysis only. Does not establish a clinical diagnosis."],
        "confidence_assessment": "High"
    }
    output = VariantExplanationOutput(**data)
    assert output.confidence_assessment == "High"
    assert len(output.supporting_evidence) == 2
    assert "TP53" in output.summary


def test_short_summary_rejected():
    data = {
        "summary": "Too short",
        "variant_context": "Valid long explanation context string here.",
        "supporting_evidence": [],
        "conflicting_evidence": [],
        "uncertainties": [],
        "missing_information": [],
        "source_references": [],
        "limitations": [],
    }
    with pytest.raises(ValidationError) as exc:
        VariantExplanationOutput(**data)
    assert "at least 10 characters" in str(exc.value)


def test_diagnostic_claim_rejected_by_guardrails():
    data = {
        "summary": "This variant diagnoses the patient with Li-Fraumeni syndrome definitively.",
        "variant_context": "Valid biological description text here.",
        "supporting_evidence": [],
        "conflicting_evidence": [],
        "uncertainties": [],
        "missing_information": [],
        "source_references": [],
        "limitations": [],
    }
    with pytest.raises(ValidationError) as exc:
        VariantExplanationOutput(**data)
    assert "prohibited clinical diagnostic phrasing detected" in str(exc.value)
