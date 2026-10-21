"""
Dataset repository for querying and managing genomic dataset records.
"""
from typing import List, Optional
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.dataset import Dataset
from app.repositories.base import BaseRepository


class DatasetRepository(BaseRepository[Dataset]):
    def __init__(self):
        super().__init__(Dataset)

    def get_by_checksum(self, db: Session, checksum: str) -> Optional[Dataset]:
        stmt = select(Dataset).where(Dataset.file_checksum == checksum)
        return db.scalars(stmt).first()

    def get_by_user(self, db: Session, user_id: str, skip: int = 0, limit: int = 50) -> List[Dataset]:
        stmt = select(Dataset).where(Dataset.user_id == user_id).offset(skip).limit(limit)
        return list(db.scalars(stmt).all())

    def count(self, db: Session) -> int:
        stmt = select(Dataset)
        return len(list(db.scalars(stmt).all()))


dataset_repo = DatasetRepository()

