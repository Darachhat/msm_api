from datetime import date, datetime
from decimal  import Decimal
from typing   import List, Optional
from uuid     import UUID

from fastapi        import HTTPException, status
from sqlalchemy.orm import Session, joinedload

from app.core.enum              import STATUS_CODE_ENUM
from app.core.log               import logger
from app.models.base_data_model import MEDICINE_MODEL
from app.models.data_model      import (
    PATIENT_DISPENSING_ITEM_MODEL
    , PATIENT_DISPENSING_MODEL
    , PATIENT_MODEL
    , STOCK_LEDGER_MODEL
)
from app.schemas.dispensing_schema import (
    DispensingCreate
    , DispensingItemInput
    , DispensingItemResponse
    , DispensingResponse
    , DispensingUpdate
)


class DispensingService:

    @staticmethod
    def _resolve_medicine(session: Session, item: DispensingItemInput) -> MEDICINE_MODEL:
        med = None
        if item.medicine_id:
            med = (
                session.query(MEDICINE_MODEL)
                .filter(
                    MEDICINE_MODEL.id == item.medicine_id
                    , MEDICINE_MODEL.deleted_datetime.is_(None)
                )
                .first()
            )
        elif item.medicine_code:
            med = (
                session.query(MEDICINE_MODEL)
                .filter(
                    MEDICINE_MODEL.code == item.medicine_code
                    , MEDICINE_MODEL.deleted_datetime.is_(None)
                )
                .first()
            )
        if not med:
            logger.warn(
                "DispensingService._resolve_medicine: medicine not found"
                , f"medicine_id: {item.medicine_id}"
                , f"medicine_code: {item.medicine_code}"
            )
            raise HTTPException(
                status_code = status.HTTP_404_NOT_FOUND
                , detail    = f"Medicine not found (id={item.medicine_id}, code={item.medicine_code})."
            )
        return med


    @staticmethod
    def _sync_stock_usage(
        session           : Session
        , stock_date      : date
        , department_code : str
        , medicine_id     : UUID
        , delta_qty       : Decimal
        , username        : str
    ) -> None:
        ledger = (
            session.query(STOCK_LEDGER_MODEL)
            .filter(
                STOCK_LEDGER_MODEL.stock_date == stock_date
                , STOCK_LEDGER_MODEL.department_code == department_code
                , STOCK_LEDGER_MODEL.medicine_id == medicine_id
            )
            .first()
        )
        if not ledger:
            ledger = STOCK_LEDGER_MODEL(
                stock_date        = stock_date
                , department_code = department_code
                , medicine_id     = medicine_id
                , opening_qty     = Decimal("0")
                , added_qty       = Decimal("0")
                , used_qty        = max(Decimal("0"), delta_qty)
                , remaining_qty   = Decimal("0") - max(Decimal("0"), delta_qty)
                , created_by      = username
            )
            session.add(ledger)
        else:
            ledger.used_qty = max(Decimal("0"), (ledger.used_qty or Decimal("0")) + delta_qty)
            ledger.remaining_qty = (
                (ledger.opening_qty or Decimal("0"))
                + (ledger.added_qty or Decimal("0"))
                - ledger.used_qty
            )
            ledger.updated_by       = username
            ledger.updated_datetime = datetime.utcnow()


    @staticmethod
    def _to_response(record: PATIENT_DISPENSING_MODEL) -> DispensingResponse:
        items = [
            DispensingItemResponse(
                id               = it.id
                , medicine_id    = it.medicine_id
                , medicine_code  = it.medicine.code if it.medicine else None
                , medicine_name  = it.medicine.name if it.medicine else None
                , quantity       = it.quantity
                , signature_id   = it.signature_id
                , signature_note = it.signature_note
                , note           = it.note
            )
            for it in record.items
            if it.deleted_datetime is None
        ]
        return DispensingResponse(
            id                 = record.id
            , patient_id       = record.patient_id
            , dispense_date    = record.dispense_date
            , department_code  = record.department_code
            , category_code    = record.category_code
            , patient_no       = record.patient_no
            , patient_name     = record.patient_name
            , age              = record.age
            , sex              = record.sex
            , diagnostic       = record.diagnostic
            , address_province = record.address_province
            , doctor_name      = record.doctor_name
            , duty_chief_name  = record.duty_chief_name
            , prepared_by_name = record.prepared_by_name
            , note             = record.note
            , status_code      = record.status_code
            , created_datetime = record.created_datetime
            , items            = items
        )


    @classmethod
    def create_dispensing(
        cls
        , session  : Session
        , payload  : DispensingCreate
        , username : str
    ) -> DispensingResponse:
        patient_name     = payload.patient_name
        age              = payload.age
        sex              = payload.sex
        diagnostic       = payload.diagnostic
        address_province = payload.address_province

        if payload.patient_id:
            p = (
                session.query(PATIENT_MODEL)
                .filter(
                    PATIENT_MODEL.id == payload.patient_id
                    , PATIENT_MODEL.deleted_datetime.is_(None)
                )
                .first()
            )
            if not p:
                raise HTTPException(
                    status_code = status.HTTP_404_NOT_FOUND
                    , detail    = "Patient not found."
                )
            patient_name     = patient_name or p.full_name
            age              = age or p.age
            sex              = sex or p.sex
            diagnostic       = diagnostic or p.diagnostic
            address_province = address_province or p.pob_province

        if not patient_name:
            raise HTTPException(
                status_code = status.HTTP_422_UNPROCESSABLE_ENTITY
                , detail    = "Either patient_id or patient_name must be provided."
            )

        record = PATIENT_DISPENSING_MODEL(
            patient_id         = payload.patient_id
            , dispense_date    = payload.dispense_date
            , department_code  = payload.department_code
            , category_code    = payload.category_code
            , patient_no       = payload.patient_no
            , patient_name     = patient_name
            , age              = age
            , sex              = sex
            , diagnostic       = diagnostic
            , address_province = address_province
            , doctor_name      = payload.doctor_name
            , duty_chief_name  = payload.duty_chief_name
            , prepared_by_name = payload.prepared_by_name
            , note             = payload.note
            , created_by       = username
        )
        session.add(record)
        session.flush()

        for item_in in payload.items:
            med  = cls._resolve_medicine(session, item_in)
            item = PATIENT_DISPENSING_ITEM_MODEL(
                dispensing_id    = record.id
                , medicine_id    = med.id
                , quantity       = item_in.quantity
                , signature_id   = item_in.signature_id
                , signature_note = item_in.signature_note
                , note           = item_in.note
                , created_by     = username
            )
            session.add(item)
            if payload.sync_stock_ledger:
                cls._sync_stock_usage(
                    session           = session
                    , stock_date      = payload.dispense_date
                    , department_code = payload.department_code
                    , medicine_id     = med.id
                    , delta_qty       = item_in.quantity
                    , username        = username
                )

        session.commit()
        logger.info(
            "DispensingService.create_dispensing: created"
            , f"dispensing_id: {record.id}"
            , f"department_code: {payload.department_code}"
            , f"items_count: {len(payload.items)}"
            , f"username: {username}"
        )
        return cls.get_dispensing(session, record.id)


    @classmethod
    def list_dispensing(
        cls
        , session         : Session
        , start_date      : Optional[date] = None
        , end_date        : Optional[date] = None
        , category_code   : Optional[str]  = None
        , department_code : Optional[str]  = None
    ) -> List[DispensingResponse]:
        query = (
            session.query(PATIENT_DISPENSING_MODEL)
            .options(joinedload(PATIENT_DISPENSING_MODEL.items).joinedload(PATIENT_DISPENSING_ITEM_MODEL.medicine))
            .filter(
                PATIENT_DISPENSING_MODEL.status_code == STATUS_CODE_ENUM.ACTIVE.value
                , PATIENT_DISPENSING_MODEL.deleted_datetime.is_(None)
            )
        )
        if start_date:
            query = query.filter(PATIENT_DISPENSING_MODEL.dispense_date >= start_date)
        if end_date:
            query = query.filter(PATIENT_DISPENSING_MODEL.dispense_date <= end_date)
        if category_code:
            query = query.filter(PATIENT_DISPENSING_MODEL.category_code == category_code)
        if department_code:
            query = query.filter(PATIENT_DISPENSING_MODEL.department_code == department_code)

        rows = query.order_by(
            PATIENT_DISPENSING_MODEL.dispense_date.desc()
            , PATIENT_DISPENSING_MODEL.patient_no
        ).all()
        return [cls._to_response(r) for r in rows]


    @classmethod
    def get_dispensing(cls, session: Session, dispensing_id: UUID) -> DispensingResponse:
        record = (
            session.query(PATIENT_DISPENSING_MODEL)
            .options(joinedload(PATIENT_DISPENSING_MODEL.items).joinedload(PATIENT_DISPENSING_ITEM_MODEL.medicine))
            .filter(
                PATIENT_DISPENSING_MODEL.id == dispensing_id
                , PATIENT_DISPENSING_MODEL.deleted_datetime.is_(None)
            )
            .first()
        )
        if not record:
            logger.warn(
                "DispensingService.get_dispensing: not found"
                , f"dispensing_id: {dispensing_id}"
            )
            raise HTTPException(
                status_code = status.HTTP_404_NOT_FOUND
                , detail    = "Dispensing record not found."
            )
        return cls._to_response(record)


    @classmethod
    def update_dispensing(
        cls
        , session       : Session
        , dispensing_id : UUID
        , payload       : DispensingUpdate
        , username      : str
    ) -> DispensingResponse:
        record = (
            session.query(PATIENT_DISPENSING_MODEL)
            .filter(
                PATIENT_DISPENSING_MODEL.id == dispensing_id
                , PATIENT_DISPENSING_MODEL.deleted_datetime.is_(None)
            )
            .first()
        )
        if not record:
            raise HTTPException(
                status_code = status.HTTP_404_NOT_FOUND
                , detail    = "Dispensing record not found."
            )

        data = payload.model_dump(exclude_unset = True, exclude = {"items"})
        for k, v in data.items():
            setattr(record, k, v)
        record.updated_by       = username
        record.updated_datetime = datetime.utcnow()

        if payload.items is not None:
            session.query(PATIENT_DISPENSING_ITEM_MODEL).filter(
                PATIENT_DISPENSING_ITEM_MODEL.dispensing_id == record.id
            ).delete()
            for item_in in payload.items:
                med = cls._resolve_medicine(session, item_in)
                session.add(
                    PATIENT_DISPENSING_ITEM_MODEL(
                        dispensing_id    = record.id
                        , medicine_id    = med.id
                        , quantity       = item_in.quantity
                        , signature_note = item_in.signature_note
                        , note           = item_in.note
                        , created_by     = username
                    )
                )

        session.commit()
        logger.info(
            "DispensingService.update_dispensing: updated"
            , f"dispensing_id: {dispensing_id}"
            , f"username: {username}"
        )
        return cls.get_dispensing(session, record.id)


    @classmethod
    def delete_dispensing(cls, session: Session, dispensing_id: UUID, username: str) -> None:
        record = (
            session.query(PATIENT_DISPENSING_MODEL)
            .filter(
                PATIENT_DISPENSING_MODEL.id == dispensing_id
                , PATIENT_DISPENSING_MODEL.deleted_datetime.is_(None)
            )
            .first()
        )
        if not record:
            logger.warn(
                "DispensingService.delete_dispensing: not found"
                , f"dispensing_id: {dispensing_id}"
                , f"username: {username}"
            )
            raise HTTPException(
                status_code = status.HTTP_404_NOT_FOUND
                , detail    = "Dispensing record not found."
            )
        record.status_code      = STATUS_CODE_ENUM.DELETED.value
        record.deleted_by       = username
        record.deleted_datetime = datetime.utcnow()
        session.commit()
        logger.info(
            "DispensingService.delete_dispensing: soft-deleted"
            , f"dispensing_id: {dispensing_id}"
            , f"username: {username}"
        )
