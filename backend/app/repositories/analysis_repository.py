"""
Analysis repository for tracking analysis jobs and recording workflow state transitions.
"""
from datetime import datetime, timezone
from typing import List, Optional
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.analysis import AnalysisJob, WorkflowEvent
from app.repositories.base import BaseRepository


class AnalysisRepository(BaseRepository[AnalysisJob]):
    def __init__(self):
        super().__init__(AnalysisJob)

    def update_status(
        self,
        db: Session,
        job_id: str,
        status: str,
        current_stage: str,
        error_code: Optional[str] = None,
        error_summary: Optional[str] = None
    ) -> Optional[AnalysisJob]:
        job = self.get(db, job_id)
        if not job:
            return None

        job.status = status
        job.current_stage = current_stage
        if error_code:
            job.error_code = error_code
        if error_summary:
            job.error_summary = error_summary

        if status == "RUNNING" and not job.started_at:
            job.started_at = datetime.now(timezone.utc)
        elif status in ["COMPLETED", "FAILED", "CANCELLED"]:
            job.finished_at = datetime.now(timezone.utc)

        db.commit()
        db.refresh(job)
        return job

    def add_event(
        self,
        db: Session,
        job_id: str,
        stage: str,
        event_type: str,
        message: str,
        details: Optional[dict] = None
    ) -> WorkflowEvent:
        event = WorkflowEvent(
            analysis_id=job_id,
            stage=stage,
            event_type=event_type,
            message=message,
            details_json=details
        )
        db.add(event)
        db.commit()
        db.refresh(event)
        return event

    def get_events(self, db: Session, job_id: str) -> List[WorkflowEvent]:
        stmt = select(WorkflowEvent).where(WorkflowEvent.analysis_id == job_id).order_by(WorkflowEvent.created_at)
        return list(db.scalars(stmt).all())


analysis_repo = AnalysisRepository()

