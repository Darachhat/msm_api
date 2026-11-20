from datetime import date, timedelta
from decimal  import Decimal
from typing   import Dict, List, Optional, Tuple
from uuid     import UUID

from fastapi        import HTTPException, status
from sqlalchemy     import or_
from sqlalchemy.orm import Session, joinedload

from app.core.constants         import utc_now_naive
from app.core.enum              import REPORT_PERIOD_ENUM, STATUS_CODE_ENUM
from app.core.log               import logger
from app.models.data_model      import (
    PATIENT_DISPENSING_ITEM_MODEL
    , PATIENT_DISPENSING_MODEL
    , PATIENT_MODEL
)
from app.schemas.patient_schema import (
    PatientCreate
    , PatientMedicineUsageItem
    , PatientResponse
    , PatientUpdate
    , PatientUsageReportResponse
)


def _matches_tabs(med, tab_set: Optional[set]) -> bool:
    if not tab_set:
        return True
    if med.is_narcotic:
        return "NARCOTIC" in tab_set
    if med.category_code == "TABLET":
        return "TABLET" in tab_set or "PILL" in tab_set
    return "INJECTION" in tab_set


class PatientService:

    @staticmethod
    def to_response(patient: PATIENT_MODEL) -> PatientResponse:
        return PatientResponse(
            id                 = patient.id
            , patient_code     = patient.patient_code
            , full_name        = patient.full_name
            , sex              = patient.sex
            , age              = patient.age
            , diagnostic       = patient.diagnostic
            , pob_province     = patient.pob_province
            , date_in          = patient.date_in
            , date_out         = patient.date_out
            , admission_status = "DISCHARGED" if patient.date_out is not None else "ADMITTED"
            , note             = patient.note
            , status_code      = patient.status_code
            , created_datetime = patient.created_datetime
            , updated_datetime = patient.updated_datetime
        )


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


    @classmethod
    def create_patient(cls, session: Session, payload: PatientCreate, username: str) -> PatientResponse:
        if payload.date_out and payload.date_in and payload.date_out < payload.date_in:
            raise HTTPException(
                status_code = status.HTTP_422_UNPROCESSABLE_ENTITY
                , detail    = "Date out cannot be before date in."
            )
        patient = PATIENT_MODEL(
            patient_code   = payload.patient_code
            , full_name    = payload.full_name
            , sex          = payload.sex
            , age          = payload.age
            , diagnostic   = payload.diagnostic
            , pob_province = payload.pob_province
            , date_in      = payload.date_in
            , date_out     = payload.date_out
            , note         = payload.note
            , created_by   = username
        )
        session.add(patient)
        session.commit()
        session.refresh(patient)
        logger.info(
            "PatientService.create_patient: created"
            , f"patient_id: {patient.id}"
            , f"username: {username}"
        )
        return cls.to_response(patient)


    @classmethod
    def list_patients(
        cls
        , session          : Session
        , name             : Optional[str]  = None
        , search           : Optional[str]  = None
        , admission_status : Optional[str]  = None
        , date_in          : Optional[date] = None
        , start_date       : Optional[date] = None
        , end_date         : Optional[date] = None
        , limit            : int            = 100
        , offset           : int            = 0
    ) -> Tuple[List[PatientResponse], int]:
        query = session.query(PATIENT_MODEL).filter(
            PATIENT_MODEL.status_code == STATUS_CODE_ENUM.ACTIVE.value
            , PATIENT_MODEL.deleted_datetime.is_(None)
        )
        term = (search or name or "").strip()
        if term:
            pattern = f"%{term}%"
            query   = query.filter(
                or_(
                    PATIENT_MODEL.full_name.ilike(pattern)
                    , PATIENT_MODEL.patient_code.ilike(pattern)
                    , PATIENT_MODEL.diagnostic.ilike(pattern)
                )
            )
        if admission_status:
            st = admission_status.strip().upper()
            if st == "ADMITTED":
                query = query.filter(PATIENT_MODEL.date_out.is_(None))
            elif st == "DISCHARGED":
                query = query.filter(PATIENT_MODEL.date_out.is_not(None))
        if date_in:
            query = query.filter(PATIENT_MODEL.date_in == date_in)
        if start_date:
            query = query.filter(PATIENT_MODEL.date_in >= start_date)
        if end_date:
            query = query.filter(PATIENT_MODEL.date_in <= end_date)

        total = query.count()
        rows  = (
            query.order_by(
                PATIENT_MODEL.date_in.desc()
                , PATIENT_MODEL.created_datetime.desc()
                , PATIENT_MODEL.full_name
            )
            .offset(offset)
            .limit(limit)
            .all()
        )
        return [cls.to_response(r) for r in rows], total


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
            logger.warn(
                "PatientService.get_patient: not found"
                , f"patient_id: {patient_id}"
            )
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
    ) -> PatientResponse:
        patient  = cls.get_patient(session, patient_id)
        updates  = payload.model_dump(exclude_unset = True)
        new_in   = updates.get("date_in", patient.date_in)
        new_out  = updates.get("date_out", patient.date_out)
        if new_out and new_in and new_out < new_in:
            raise HTTPException(
                status_code = status.HTTP_422_UNPROCESSABLE_ENTITY
                , detail    = "Date out cannot be before date in."
            )
        for k, v in updates.items():
            setattr(patient, k, v)
        patient.updated_by       = username
        patient.updated_datetime = utc_now_naive()
        session.commit()
        session.refresh(patient)
        logger.info(
            "PatientService.update_patient: updated"
            , f"patient_id: {patient_id}"
            , f"username: {username}"
        )
        return cls.to_response(patient)


    @classmethod
    def delete_patient(cls, session: Session, patient_id: UUID, username: str) -> None:
        patient = cls.get_patient(session, patient_id)
        patient.status_code      = STATUS_CODE_ENUM.DELETED.value
        patient.deleted_by       = username
        patient.deleted_datetime = utc_now_naive()
        session.commit()
        logger.info(
            "PatientService.delete_patient: soft-deleted"
            , f"patient_id: {patient_id}"
            , f"username: {username}"
        )


    @classmethod
    def get_patient_usage_report(
        cls
        , session      : Session
        , start_date   : date
        , period       : str           = "DAILY"
        , end_date     : Optional[date] = None
        , tabs         : Optional[str]  = None
        , patient_id   : Optional[UUID] = None
        , patient_name : Optional[str]  = None
    ) -> List[PatientUsageReportResponse]:
        s_date, e_date = cls.resolve_period_range(start_date, period, end_date)
        tab_set = {t.strip().upper() for t in tabs.split(",") if t.strip()} if tabs else None

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

        patient_ids = {d.patient_id for d in dispensings if d.patient_id}
        patients_by_id: Dict[UUID, PATIENT_MODEL] = {}
        if patient_ids:
            patient_rows = (
                session.query(PATIENT_MODEL)
                .filter(
                    PATIENT_MODEL.id.in_(patient_ids)
                    , PATIENT_MODEL.deleted_datetime.is_(None)
                )
                .all()
            )
            patients_by_id = {p.id: p for p in patient_rows}

        for d in dispensings:
            key = str(d.patient_id) if d.patient_id else d.patient_name.strip().lower()
            for it in d.items:
                if it.deleted_datetime is not None or not it.medicine:
                    continue
                m = it.medicine
                if not _matches_tabs(m, tab_set):
                    continue
                if key not in grouped:
                    p_rec = patients_by_id.get(d.patient_id) if d.patient_id else None
                    grouped[key] = {
                        "patient_id"     : d.patient_id
                        , "patient_code" : p_rec.patient_code if p_rec else None
                        , "patient_name" : p_rec.full_name if p_rec else d.patient_name
                        , "sex"          : p_rec.sex if p_rec else d.sex
                        , "age"          : p_rec.age if p_rec else d.age
                        , "diagnostic"   : p_rec.diagnostic if p_rec else d.diagnostic
                        , "pob_province" : p_rec.pob_province if p_rec else d.address_province
                        , "date_in"      : p_rec.date_in if p_rec else None
                        , "meds"         : {}
                    }
                meds_map = grouped[key]["meds"]
                if m.id not in meds_map:
                    meds_map[m.id] = {
                        "item"   : PatientMedicineUsageItem(
                            medicine_id      = m.id
                            , medicine_code  = m.code
                            , medicine_name  = m.name
                            , category_code  = m.category_code
                            , is_narcotic    = m.is_narcotic
                            , form_code      = m.form_code
                            , dosage         = m.dosage
                            , sort_order     = m.sort_order or 0
                            , total_quantity = Decimal("0")
                            , days_count     = 0
                        )
                        , "days" : set()
                    }
                meds_map[m.id]["item"].total_quantity += it.quantity or Decimal("0")
                meds_map[m.id]["days"].add(d.dispense_date)

        output: List[PatientUsageReportResponse] = []
        for v in grouped.values():
            meds_list: List[PatientMedicineUsageItem] = []
            for entry in v["meds"].values():
                entry["item"].days_count = len(entry["days"])
                meds_list.append(entry["item"])
            meds_list.sort(key = lambda x: (x.sort_order, x.medicine_name))
            output.append(
                PatientUsageReportResponse(
                    patient_id       = v["patient_id"]
                    , patient_code   = v["patient_code"]
                    , patient_name   = v["patient_name"]
                    , sex            = v["sex"]
                    , age            = v["age"]
                    , diagnostic     = v["diagnostic"]
                    , pob_province   = v["pob_province"]
                    , date_in        = v["date_in"]
                    , start_date     = s_date
                    , end_date       = e_date
                    , medicines      = meds_list
                )
            )
        return output
