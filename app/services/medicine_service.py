from datetime import datetime
from typing   import List, Optional
from uuid     import UUID

from fastapi        import HTTPException, status
from sqlalchemy.orm import Session

from app.core.enum              import STATUS_CODE_ENUM
from app.models.base_data_model import (
    DEPARTMENT_MODEL
    , MEDICINE_CATEGORY_MODEL
    , MEDICINE_FORM_MODEL
    , MEDICINE_MODEL
)
from app.schemas.medicine_schema import MedicineCreate, MedicineUpdate


class MedicineService:

    @staticmethod
    def list_medicines(
        session           : Session
        , category_code   : Optional[str] = None
        , is_narcotic     : Optional[bool] = None
        , search          : Optional[str] = None
    ) -> List[MEDICINE_MODEL]:
        query = session.query(MEDICINE_MODEL).filter(
            MEDICINE_MODEL.status_code == STATUS_CODE_ENUM.ACTIVE.value
            , MEDICINE_MODEL.deleted_datetime.is_(None)
        )
        if category_code:
            query = query.filter(MEDICINE_MODEL.category_code == category_code)
        if is_narcotic is not None:
            query = query.filter(MEDICINE_MODEL.is_narcotic == is_narcotic)
        if search:
            query = query.filter(MEDICINE_MODEL.name.ilike(f"%{search}%"))
        return query.order_by(
            MEDICINE_MODEL.category_code
            , MEDICINE_MODEL.sort_order
            , MEDICINE_MODEL.name
        ).all()


    @staticmethod
    def get_medicine(session: Session, medicine_id: UUID) -> MEDICINE_MODEL:
        med = (
            session.query(MEDICINE_MODEL)
            .filter(
                MEDICINE_MODEL.id == medicine_id
                , MEDICINE_MODEL.deleted_datetime.is_(None)
            )
            .first()
        )
        if not med:
            raise HTTPException(
                status_code = status.HTTP_404_NOT_FOUND
                , detail    = "Medicine not found."
            )
        return med


    @staticmethod
    def create_medicine(session: Session, payload: MedicineCreate, username: str) -> MEDICINE_MODEL:
        existing = session.query(MEDICINE_MODEL).filter(MEDICINE_MODEL.code == payload.code).first()
        if existing:
            raise HTTPException(
                status_code = status.HTTP_409_CONFLICT
                , detail    = "Medicine code already exists."
            )

        med = MEDICINE_MODEL(
            **payload.model_dump()
            , created_by = username
        )
        session.add(med)
        session.commit()
        session.refresh(med)
        return med


    @classmethod
    def update_medicine(
        cls
        , session     : Session
        , medicine_id : UUID
        , payload     : MedicineUpdate
        , username    : str
    ) -> MEDICINE_MODEL:
        med = cls.get_medicine(session, medicine_id)
        for field, value in payload.model_dump(exclude_unset = True).items():
            setattr(med, field, value)
        med.updated_by       = username
        med.updated_datetime = datetime.utcnow()
        session.commit()
        session.refresh(med)
        return med


    @classmethod
    def delete_medicine(cls, session: Session, medicine_id: UUID, username: str) -> None:
        med = cls.get_medicine(session, medicine_id)
        med.status_code      = STATUS_CODE_ENUM.DELETED.value
        med.deleted_by       = username
        med.deleted_datetime = datetime.utcnow()
        session.commit()


    @staticmethod
    def list_departments(session: Session) -> List[DEPARTMENT_MODEL]:
        return (
            session.query(DEPARTMENT_MODEL)
            .filter(DEPARTMENT_MODEL.status_code == STATUS_CODE_ENUM.ACTIVE.value)
            .all()
        )


    @staticmethod
    def list_categories(session: Session) -> List[MEDICINE_CATEGORY_MODEL]:
        return (
            session.query(MEDICINE_CATEGORY_MODEL)
            .filter(MEDICINE_CATEGORY_MODEL.status_code == STATUS_CODE_ENUM.ACTIVE.value)
            .order_by(MEDICINE_CATEGORY_MODEL.record_order)
            .all()
        )


    @staticmethod
    def list_forms(session: Session) -> List[MEDICINE_FORM_MODEL]:
        return (
            session.query(MEDICINE_FORM_MODEL)
            .filter(MEDICINE_FORM_MODEL.status_code == STATUS_CODE_ENUM.ACTIVE.value)
            .order_by(MEDICINE_FORM_MODEL.record_order)
            .all()
        )
