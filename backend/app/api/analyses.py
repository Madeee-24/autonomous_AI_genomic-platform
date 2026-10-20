"""
REST API Router for genomic analysis job management, stage polling, and cancellations.
"""
from typing import List
from fastapi import APIRouter, BackgroundTasks, Depends, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.analysis import (
    AnalysisCreateRequest,
    AnalysisListResponse,
    AnalysisResponse,
    WorkflowEventResponse,
)
from app.schemas.dataset import ErrorResponse
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

