"""
Report Repository: Handles database queries and persistence for generated PDF reports.
"""
from typing import List, Optional
from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from app.models.report import Report
from app.repositories.base import BaseRepository


class ReportRepository(BaseRepository[Report]):
    def __init__(self):
        super().__init__(Report)

    def get_by_analysis(self, db: Session, analysis_id: str) -> List[Report]:
        """
        Retrieves all report records generated for a specific analysis job, ordered by date descending.
        """
        stmt = (
            select(Report)
            .where(Report.analysis_id == analysis_id)
            .order_by(desc(Report.created_at))
        )
        return list(db.scalars(stmt).all())

    def get_latest_by_analysis(self, db: Session, analysis_id: str) -> Optional[Report]:
        """
        Retrieves the most recently generated report record for an analysis.
        """
        stmt = (
            select(Report)
            .where(Report.analysis_id == analysis_id)
            .order_by(desc(Report.created_at))
            .limit(1)
        )
        return db.scalars(stmt).first()


report_repo = ReportRepository()
