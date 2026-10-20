"""
Pydantic schemas for analysis job creation, status polling, and workflow events.
"""
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class AnalysisOptions(BaseModel):
    annotate_with_vep: bool = Field(False, description="Enable Ensembl VEP consequence annotation")
    retrieve_clinvar_evidence: bool = Field(False, description="Enable NCBI ClinVar evidence retrieval")
    generate_ai_explanations: bool = Field(False, description="Enable grounded AI explanations")


class AnalysisCreateRequest(BaseModel):
    """
    Request body for creating and queuing a new genomic analysis.
    """
    dataset_id: str = Field(..., description="UUID of the uploaded dataset")
    genome_assembly: str = Field("GRCh38", description="Target genome assembly (GRCh38 or GRCh37)")
    options: AnalysisOptions = Field(default_factory=AnalysisOptions, description="Analysis feature flags")


class WorkflowEventResponse(BaseModel):
    """
    Schema for workflow audit trail events.
    """
    id: str
    stage: str
    event_type: str
    message: str
    details: Optional[Dict[str, Any]] = None
    created_at: str


class AnalysisResponse(BaseModel):
    """
    Full response model for an analysis job and its current processing state.
    """
    id: str
    dataset_id: str
    status: str
    current_stage: str
    variants_count: int = 0
    configuration: Optional[Dict[str, Any]] = None
    created_at: str
    started_at: Optional[str] = None
    finished_at: Optional[str] = None
    error_code: Optional[str] = None
    error_summary: Optional[str] = None


class AnalysisListResponse(BaseModel):
    """
    Paginated list of analysis jobs.
    """
    total: int
    items: List[AnalysisResponse]

