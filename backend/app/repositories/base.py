"""
Generic Base Repository providing standard CRUD abstractions.
"""
from typing import Any, Generic, List, Optional, Type, TypeVar
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.base import Base

ModelType = TypeVar("ModelType", bound=Base)


class BaseRepository(Generic[ModelType]):
    """
    Base repository implementing reusable data access methods.
    """

    def __init__(self, model: Type[ModelType]):
        self.model = model

    def get(self, db: Session, id: Any) -> Optional[ModelType]:
        return db.get(self.model, id)

    def get_multi(self, db: Session, skip: int = 0, limit: int = 100) -> List[ModelType]:
        stmt = select(self.model).offset(skip).limit(limit)
        return list(db.scalars(stmt).all())

    def create(self, db: Session, obj_in: ModelType) -> ModelType:
        db.add(obj_in)
        db.commit()
        db.refresh(obj_in)
        return obj_in

    def delete(self, db: Session, id: Any) -> bool:
        obj = self.get(db, id)
        if obj:
            db.delete(obj)
            db.commit()
            return True
        return False

