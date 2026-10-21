"""
Pydantic schemas for genomic variants, consequence annotations, clinical evidence, and prioritization query responses.
"""
from datetime import datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class AnnotationSummary(BaseModel):
    id: str
    gene_symbol: Optional[str] = None
    gene_id: Optional[str] = None
    transcript_id: Optional[str] = None
    consequence: str
    impact: str
    annotation_source: str = "Ensembl VEP"
    annotation_version: Optional[str] = None


class EvidenceSummary(BaseModel):
    id: str
    source_name: str = "ClinVar"
    source_accession: Optional[str] = None
    interpretation: str
    review_status: Optional[str] = None
    evidence_summary: Optional[str] = None
    source_url: Optional[str] = None
    has_conflicts: bool = False
    retrieved_at: Optional[datetime] = None


class PrioritizationSummary(BaseModel):
    id: str
    rule_version: str = "v1.0"
    score: Optional[float] = None
    priority_category: str
    reasons: Optional[Dict[str, Any]] = None
    limitations: Optional[Dict[str, Any]] = None


class AIExplanationSummary(BaseModel):
    id: str
    model_provider: str
    model_name: str
    prompt_version: str = "v1.0"
    explanation_text: str
    validation_status: str = "VALID"
    structured_output: Optional[Dict[str, Any]] = None
    created_at: Optional[datetime] = None


class VariantItemResponse(BaseModel):
    id: str
    analysis_id: str
    chromosome: str
    position: int
    reference_allele: str
    alternate_allele: str
    variant_identifier: Optional[str] = None
    variant_type: str = "SNV"
    quality: Optional[float] = None
    filter_status: str = "PASS"
    is_multiallelic: bool = False
    
    # Flattened primary annotation & evidence for fast table rendering
    primary_gene: Optional[str] = None
    primary_consequence: Optional[str] = None
    primary_impact: Optional[str] = None
    
    clinvar_interpretation: Optional[str] = None
    clinvar_review_status: Optional[str] = None
    clinvar_accession: Optional[str] = None
    has_conflicts: bool = False
    
    priority_category: Optional[str] = None
    priority_score: Optional[float] = None
    
    # Full nested objects
    annotations: List[AnnotationSummary] = []
    evidence_records: List[EvidenceSummary] = []
    prioritization: Optional[PrioritizationSummary] = None
    ai_explanation: Optional[AIExplanationSummary] = None


class VariantDetailResponse(VariantItemResponse):
    info_json: Optional[Dict[str, Any]] = None
    genotype_json: Optional[Dict[str, Any]] = None


class VariantListResponse(BaseModel):
    total: int
    page: int
    page_size: int
    total_pages: int
    items: List[VariantItemResponse]


class AnalysisStatisticsResponse(BaseModel):
    analysis_id: str
    total_variants: int
    annotated_variants: int
    evidence_variants: int
    prioritized_variants: int
    annotation_coverage_pct: float
    evidence_coverage_pct: float
    
    tier_counts: Dict[str, int]
    consequence_counts: Dict[str, int]
    impact_counts: Dict[str, int]
    clinvar_counts: Dict[str, int]


class DashboardSummaryResponse(BaseModel):
    total_datasets: int
    total_analyses: int
    running_analyses: int
    completed_analyses: int
    failed_analyses: int
    total_variants_processed: int
    average_annotation_coverage_pct: float
    average_evidence_coverage_pct: float
    tier_distribution: Dict[str, int]

