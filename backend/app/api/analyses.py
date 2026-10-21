"""
REST API Router for genomic analysis job management, stage polling, variant exploration, and statistics.
"""
from typing import List, Optional
from fastapi import APIRouter, BackgroundTasks, Depends, Query, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.analysis import (
    AnalysisCreateRequest,
    AnalysisListResponse,
    AnalysisResponse,
    WorkflowEventResponse,
)
from app.schemas.dataset import ErrorResponse
from app.schemas.variant import (
    AnalysisStatisticsResponse,
    DashboardSummaryResponse,
    VariantDetailResponse,
    VariantListResponse,
)
from app.services.analysis_service import analysis_service

router = APIRouter()


@router.post(
    "",
    response_model=AnalysisResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Create and start a genomic analysis",
    description="Initializes an asynchronous pipeline job for a validated dataset and triggers background processing.",
    responses={
        400: {"model": ErrorResponse, "description": "Invalid dataset or storage error"},
        404: {"model": ErrorResponse, "description": "Dataset not found"}
    }
)
async def create_analysis(
    request: AnalysisCreateRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    return analysis_service.create_analysis(db, request, background_tasks)


@router.get(
    "/dashboard/summary",
    response_model=DashboardSummaryResponse,
    summary="Get dashboard overview metrics",
    description="Aggregates system-wide counts of datasets, analysis jobs, processed variants, and priority tiers."
)
async def get_dashboard_summary(
    db: Session = Depends(get_db)
):
    return analysis_service.get_dashboard_summary(db)


@router.get(
    "",
    response_model=AnalysisListResponse,
    summary="List analysis jobs",
    description="Returns all submitted analysis jobs with status, stage, and variant counts."
)
async def list_analyses(
    skip: int = 0,
    limit: int = 50,
    db: Session = Depends(get_db)
):
    return analysis_service.list_analyses(db, skip=skip, limit=limit)


@router.get(
    "/{analysis_id}",
    response_model=AnalysisResponse,
    summary="Get analysis status",
    description="Retrieves current execution stage, overall status, timing, and variant count for a specific job.",
    responses={
        404: {"model": ErrorResponse, "description": "Analysis job not found"}
    }
)
async def get_analysis(
    analysis_id: str,
    db: Session = Depends(get_db)
):
    return analysis_service.get_analysis(db, analysis_id)


@router.get(
    "/{analysis_id}/events",
    response_model=List[WorkflowEventResponse],
    summary="Get workflow audit events",
    description="Returns chronological stage transitions, warnings, and error logs for an analysis job.",
    responses={
        404: {"model": ErrorResponse, "description": "Analysis job not found"}
    }
)
async def get_analysis_events(
    analysis_id: str,
    db: Session = Depends(get_db)
):
    return analysis_service.get_events(db, analysis_id)


@router.get(
    "/{analysis_id}/statistics",
    response_model=AnalysisStatisticsResponse,
    summary="Get analysis statistics and breakdown",
    description="Returns variant distributions by consequence, impact, ClinVar status, and priority tier.",
    responses={
        404: {"model": ErrorResponse, "description": "Analysis job not found"}
    }
)
async def get_analysis_statistics(
    analysis_id: str,
    db: Session = Depends(get_db)
):
    return analysis_service.get_statistics(db, analysis_id)


@router.get(
    "/{analysis_id}/variants",
    response_model=VariantListResponse,
    summary="List paginated and filtered variants for an analysis",
    description="Provides server-side filtering by chromosome, gene symbol, consequence, priority tier, and search query.",
    responses={
        404: {"model": ErrorResponse, "description": "Analysis job not found"}
    }
)
async def get_analysis_variants(
    analysis_id: str,
    chromosome: Optional[str] = Query(None, description="Filter by chromosome (e.g. chr17, chr7, 17)"),
    gene: Optional[str] = Query(None, description="Filter by gene symbol (e.g. TP53, CFTR)"),
    consequence: Optional[str] = Query(None, description="Filter by consequence term (e.g. missense_variant)"),
    priority_category: Optional[str] = Query(None, description="Filter by priority tier (e.g. TIER_1_CRITICAL)"),
    has_conflicts: Optional[bool] = Query(None, description="Filter by presence of conflicting evidence"),
    search: Optional[str] = Query(None, description="Search across dbSNP id, gene symbol, or chromosome"),
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(25, ge=1, le=200, description="Items per page"),
    db: Session = Depends(get_db)
):
    return analysis_service.get_variants(
        db=db,
        job_id=analysis_id,
        chromosome=chromosome,
        gene=gene,
        consequence=consequence,
        priority_category=priority_category,
        has_conflicts=has_conflicts,
        search=search,
        page=page,
        page_size=page_size,
    )


@router.get(
    "/{analysis_id}/variants/{variant_id}",
    response_model=VariantDetailResponse,
    summary="Get full variant detail with annotations and clinical evidence",
    description="Returns detailed transcript consequences, ClinVar submissions, review status, and prioritization rationale.",
    responses={
        404: {"model": ErrorResponse, "description": "Variant or analysis not found"}
    }
)
async def get_variant_detail(
    analysis_id: str,
    variant_id: str,
    db: Session = Depends(get_db)
):
    return analysis_service.get_variant_detail(db, job_id=analysis_id, variant_id=variant_id)


@router.post(
    "/{analysis_id}/cancel",
    response_model=AnalysisResponse,
    summary="Cancel analysis job",
    description="Safely halts a running or queued analysis job.",
    responses={
        400: {"model": ErrorResponse, "description": "Job cannot be cancelled"},
        404: {"model": ErrorResponse, "description": "Analysis job not found"}
    }
)
async def cancel_analysis(
    analysis_id: str,
    db: Session = Depends(get_db)
):
    return analysis_service.cancel_analysis(db, analysis_id)
