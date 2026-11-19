from datetime import date, datetime, timedelta
from decimal  import Decimal
from typing   import Dict, List, Optional
from uuid     import UUID

from fastapi        import HTTPException, status
from sqlalchemy.orm import Session, joinedload

from app.core.enum              import REPORT_PERIOD_ENUM, STATUS_CODE_ENUM
from app.models.data_model      import (
    PATIENT_DISPENSING_ITEM_MODEL
    , PATIENT_DISPENSING_MODEL
    , PATIENT_MODEL
)
from app.schemas.patient_schema import (
    PatientCreate
    , PatientMedicineUsageItem
    , PatientUpdate
    , PatientUsageReportResponse
)


class PatientService:

    @staticmethod
    def resolve_period_range(start_date: date, period: str, end_date: Optional[date] = None) -> tuple[date, date]:
        if end_date:
            return start_date, end_date
        if period == REPORT_PERIOD_ENUM.WEEKLY.value:
            return start_date, start_date + timedelta(days = 6)
        if period == REPORT_PERIOD_ENUM.MONTHLY.value:
            next_month = (start_date.replace(day = 28) + timedelta(days = 4)).replace(day = 1)
            return start_date, next_month - timedelta(days = 1)
        return start_date, start_date


    @staticmethod
    def create_patient(session: Session, payload: PatientCreate, username: str) -> PATIENT_MODEL:
        patient = PATIENT_MODEL(
            patient_code   = payload.patient_code
            , full_name    = payload.full_name
            , sex          = payload.sex
            , age          = payload.age
            , diagnostic   = payload.diagnostic
            , pob_province = payload.pob_province
            , date_in      = payload.date_in
            , note         = payload.note
            , created_by   = username
        )
        session.add(patient)
        session.commit()
        session.refresh(patient)
        return patient


    @staticmethod
    def list_patients(
        session     : Session
        , name      : Optional[str] = None
        , date_in   : Optional[date] = None
    ) -> List[PATIENT_MODEL]:
        query = session.query(PATIENT_MODEL).filter(
            PATIENT_MODEL.status_code == STATUS_CODE_ENUM.ACTIVE.value
            , PATIENT_MODEL.deleted_datetime.is_(None)
        )
        if name:
            query = query.filter(PATIENT_MODEL.full_name.ilike(f"%{name}%"))
        if date_in:
            query = query.filter(PATIENT_MODEL.date_in == date_in)
        return query.order_by(
            PATIENT_MODEL.date_in.desc()
            , PATIENT_MODEL.full_name
        ).all()


    @staticmethod
    def get_patient(session: Session, patient_id: UUID) -> PATIENT_MODEL:
        patient = (
            session.query(PATIENT_MODEL)
            .filter(
                PATIENT_MODEL.id == patient_id
                , PATIENT_MODEL.deleted_datetime.is_(None)
            )
            .first()
        )
        if not patient:
            raise HTTPException(
                status_code = status.HTTP_404_NOT_FOUND
                , detail    = "Patient not found."
            )
        return patient


    @classmethod
    def update_patient(
        cls
        , session    : Session
        , patient_id : UUID
        , payload    : PatientUpdate
        , username   : str
    ) -> PATIENT_MODEL:
        patient = cls.get_patient(session, patient_id)
        for k, v in payload.model_dump(exclude_unset = True).items():
            setattr(patient, k, v)
        patient.updated_by       = username
        patient.updated_datetime = datetime.utcnow()
        session.commit()
        session.refresh(patient)
        return patient


    @classmethod
    def delete_patient(cls, session: Session, patient_id: UUID, username: str) -> None:
        patient = cls.get_patient(session, patient_id)
        patient.status_code      = STATUS_CODE_ENUM.DELETED.value
        patient.deleted_by       = username
        patient.deleted_datetime = datetime.utcnow()
        session.commit()


    @classmethod
    def get_patient_usage_report(
        cls
        , session      : Session
        , start_date   : date
        , period       : str = "DAILY"
        , end_date     : Optional[date] = None
        , patient_id   : Optional[UUID] = None
        , patient_name : Optional[str] = None
    ) -> List[PatientUsageReportResponse]:
        s_date, e_date = cls.resolve_period_range(start_date, period, end_date)
        query = (
            session.query(PATIENT_DISPENSING_MODEL)
            .options(joinedload(PATIENT_DISPENSING_MODEL.items).joinedload(PATIENT_DISPENSING_ITEM_MODEL.medicine))
            .filter(
                PATIENT_DISPENSING_MODEL.dispense_date >= s_date
                , PATIENT_DISPENSING_MODEL.dispense_date <= e_date
                , PATIENT_DISPENSING_MODEL.status_code == STATUS_CODE_ENUM.ACTIVE.value
                , PATIENT_DISPENSING_MODEL.deleted_datetime.is_(None)
            )
        )
        if patient_id:
            query = query.filter(PATIENT_DISPENSING_MODEL.patient_id == patient_id)
        if patient_name:
            query = query.filter(PATIENT_DISPENSING_MODEL.patient_name.ilike(f"%{patient_name}%"))

        dispensings = query.all()
        grouped: Dict[str, dict] = {}

        for d in dispensings:
            key = str(d.patient_id) if d.patient_id else d.patient_name.strip().lower()
            if key not in grouped:
                p_rec = cls.get_patient(session, d.patient_id) if d.patient_id else None
                grouped[key] = {
                    "patient_id"      : d.patient_id
                    , "patient_name"  : p_rec.full_name if p_rec else d.patient_name
                    , "sex"           : p_rec.sex if p_rec else d.sex
                    , "age"           : p_rec.age if p_rec else d.age
                    , "diagnostic"    : p_rec.diagnostic if p_rec else d.diagnostic
                    , "pob_province"  : p_rec.pob_province if p_rec else d.address_province
                    , "date_in"       : p_rec.date_in if p_rec else None
                    , "meds"          : {}
                }
            meds_map = grouped[key]["meds"]
            for it in d.items:
                if it.deleted_datetime is not None or not it.medicine:
                    continue
                m = it.medicine
                if m.id not in meds_map:
                    meds_map[m.id] = PatientMedicineUsageItem(
                        medicine_id      = m.id
                        , medicine_code  = m.code
                        , medicine_name  = m.name
                        , category_code  = m.category_code
                        , form_code      = m.form_code
                        , dosage         = m.dosage
                        , total_quantity = Decimal("0")
                    )
                meds_map[m.id].total_quantity += it.quantity or Decimal("0")

        return [
            PatientUsageReportResponse(
                patient_id       = v["patient_id"]
                , patient_name   = v["patient_name"]
                , sex            = v["sex"]
                , age            = v["age"]
                , diagnostic     = v["diagnostic"]
                , pob_province   = v["pob_province"]
                , date_in        = v["date_in"]
                , start_date     = s_date
                , end_date       = e_date
                , medicines      = list(v["meds"].values())
            )
            for v in grouped.values()
        ]
