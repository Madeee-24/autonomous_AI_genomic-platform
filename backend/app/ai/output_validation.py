"""
Pydantic validation schemas and guardrails for structured, evidence-grounded AI explanations.
Enforces academic research boundaries and structural integrity on LLM responses.
"""
import re
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field, field_validator


class EvidenceReference(BaseModel):
    source_name: str = Field(..., description="Name of external database, e.g. NCBI ClinVar or Ensembl VEP")
    accession: Optional[str] = Field(None, description="Database record accession (e.g. VCV000012374.5 or ENST...)")
    url: Optional[str] = Field(None, description="Official public web URL to source assertion")
    note: Optional[str] = Field(None, description="Contextual note regarding record status or review stars")


class VariantExplanationOutput(BaseModel):
    """
    Standardized schema for evidence-grounded AI variant explanations.
    All claims must be strictly derived from stored VEP annotations and ClinVar records.
    """
    summary: str = Field(
        ...,
        description="Concise, 2-4 sentence scientific summary synthesizing retrieved annotations and clinical records."
    )
    variant_context: str = Field(
        ...,
        description="Biological context explaining the consequence term (e.g. missense, frameshift), affected gene, and protein impact."
    )
    supporting_evidence: List[str] = Field(
        default_factory=list,
        description="Key factual findings directly supported by retrieved ClinVar records, VEP predictions, or expert panel assertions."
    )
    conflicting_evidence: List[str] = Field(
        default_factory=list,
        description="Explicit enumeration of any disagreements between submitters, conflicting pathogenicity classifications, or discordant functional tools."
    )
    uncertainties: List[str] = Field(
        default_factory=list,
        description="Methodological uncertainties such as VUS classifications, lack of experimental functional assays, or uncharacterized transcript effects."
    )
    missing_information: List[str] = Field(
        default_factory=list,
        description="Explicit gaps in available data (e.g. absent population allele frequencies, lack of ACMG criteria details, unverified somatic vs germline status)."
    )
    source_references: List[str] = Field(
        default_factory=list,
        description="Verified database accessions and URLs provided in the context."
    )
    limitations: List[str] = Field(
        default_factory=list,
        description="Mandatory methodological caveats and academic research disclaimers."
    )
    confidence_assessment: str = Field(
        "Moderate",
        description="Qualitative assessment of evidence completeness: 'High', 'Moderate', 'Low', or 'Insufficient Evidence'."
    )

    @field_validator("summary", "variant_context")
    @classmethod
    def validate_non_empty_strings(cls, v: str) -> str:
        trimmed = v.strip()
        if len(trimmed) < 10:
            raise ValueError("Explanation fields must contain meaningful descriptive text (at least 10 characters).")
        return trimmed

    @field_validator("summary")
    @classmethod
    def reject_unsupported_diagnostic_claims(cls, v: str) -> str:
        prohibited_phrases = [
            r"\bdiagnoses\b",
            r"\bpatient has\b",
            r"\bdefinitive proof of disease\b",
            r"\byou have\b",
            r"\bclinical prescription\b",
        ]
        lower_v = v.lower()
        for pattern in prohibited_phrases:
            if re.search(pattern, lower_v):
                raise ValueError(
                    f"AI explanation violates research boundaries: prohibited clinical diagnostic phrasing detected ('{pattern}')."
                )
        return v


class ExplanationGenerationResult(BaseModel):
    """
    Encapsulates the complete LLM response, parsed payload, timing, and validation status.
    """
    model_provider: str
    model_name: str
    prompt_version: str
    is_valid: bool
    parsed_output: Optional[VariantExplanationOutput] = None
    raw_response: Optional[str] = None
    validation_errors: Optional[List[str]] = None
    input_evidence_ids: Dict[str, Any] = Field(default_factory=dict)
