from datetime import date
from decimal  import Decimal
from typing   import Dict, List, Optional, Tuple
from uuid     import UUID

from fastapi        import HTTPException, status
from sqlalchemy     import and_, or_
from sqlalchemy.orm import Session, joinedload

from app.core.constants         import utc_now_naive
from app.core.enum              import STATUS_CODE_ENUM
from app.core.log               import logger
from app.models.base_data_model import MEDICINE_MODEL
from app.models.data_model      import (
    PATIENT_DISPENSING_ITEM_MODEL
    , PATIENT_DISPENSING_MODEL
    , PATIENT_MODEL
    , STOCK_BATCH_MODEL
    , STOCK_LEDGER_MODEL
    , STOCK_MOVEMENT_MODEL
    , USER_MODEL
)
from app.schemas.dispensing_schema import (
    DispensingCreate
    , DispensingItemInput
    , DispensingItemResponse
    , DispensingLineResponse
    , DispensingResponse
    , DispensingUpdate
    , DispensingVisitCreate
)


class DispensingService:

    @staticmethod
    def _user_fullname_map(session: Session, usernames: set) -> Dict[str, str]:
        clean_names = {u for u in usernames if u}
        if not clean_names:
            return {}
        rows = (
            session.query(USER_MODEL.username, USER_MODEL.full_name)
            .filter(USER_MODEL.username.in_(clean_names))
            .all()
        )
        return {u: fn for u, fn in rows}


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
            ledger.updated_datetime = utc_now_naive()


    @staticmethod
    def _deduct_fefo(
        session              : Session
        , department_code    : str
        , med                : MEDICINE_MODEL
        , quantity           : Decimal
        , dispense_date      : date
        , dispensing_item_id : UUID
        , note               : Optional[str]
        , username           : str
    ) -> None:
        """Deduct quantity from usable batches ordered by earliest expire_date first (FEFO)."""
        today   = date.today()
        batches = (
            session.query(STOCK_BATCH_MODEL)
            .filter(
                STOCK_BATCH_MODEL.medicine_id == med.id
                , STOCK_BATCH_MODEL.department_code == department_code
                , STOCK_BATCH_MODEL.status_code == STATUS_CODE_ENUM.ACTIVE.value
                , STOCK_BATCH_MODEL.deleted_datetime.is_(None)
                , STOCK_BATCH_MODEL.remaining_qty > 0
                , or_(
                    STOCK_BATCH_MODEL.expire_date.is_(None)
                    , STOCK_BATCH_MODEL.expire_date >= today
                )
            )
            .order_by(
                STOCK_BATCH_MODEL.expire_date.asc().nullslast()
                , STOCK_BATCH_MODEL.input_date.asc()
                , STOCK_BATCH_MODEL.created_datetime.asc()
            )
            .with_for_update()
            .all()
        )
        available = sum((b.remaining_qty or Decimal("0")) for b in batches)
        if available < quantity:
            raise HTTPException(
                status_code = status.HTTP_400_BAD_REQUEST
                , detail    = f"Insufficient usable stock for '{med.name}' (available: {available}, requested: {quantity})."
            )

        remaining_to_deduct = quantity
        now_utc             = utc_now_naive()
        for b in batches:
            if remaining_to_deduct <= 0:
                break
            take = min(b.remaining_qty or Decimal("0"), remaining_to_deduct)
            if take <= 0:
                continue
            b.remaining_qty    = (b.remaining_qty or Decimal("0")) - take
            b.updated_by       = username
            b.updated_datetime = now_utc
            session.add(
                STOCK_MOVEMENT_MODEL(
                    department_code      = department_code
                    , medicine_id        = med.id
                    , batch_id           = b.id
                    , dispensing_item_id = dispensing_item_id
                    , movement_type      = "USAGE"
                    , movement_date      = dispense_date
                    , quantity           = take
                    , note               = note
                    , created_by         = username
                )
            )
            remaining_to_deduct -= take


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
            , shift_code       = record.shift_code
            , payment_code     = record.payment_code
            , doctor_name      = record.doctor_name
            , duty_chief_name  = record.duty_chief_name
            , prepared_by_name = record.prepared_by_name
            , note             = record.note
            , status_code      = record.status_code
            , created_datetime = record.created_datetime
            , items            = items
        )


    @staticmethod
    def _line_to_response(
        it         : PATIENT_DISPENSING_ITEM_MODEL
        , user_map : Optional[Dict[str, str]] = None
    ) -> DispensingLineResponse:
        d = it.dispensing
        m = it.medicine
        creator = it.created_by or (d.created_by if d else None)
        return DispensingLineResponse(
            id                 = it.id
            , dispensing_id    = it.dispensing_id
            , medicine_id      = it.medicine_id
            , medicine_code    = m.code if m else None
            , medicine_name    = m.name if m else None
            , form_code        = m.form_code if m else None
            , dosage           = m.dosage if m else None
            , category_code    = m.category_code if m else None
            , is_narcotic      = bool(m.is_narcotic) if m else False
            , patient_id       = d.patient_id if d else None
            , patient_name     = d.patient_name if d else ""
            , sex              = d.sex if d else None
            , age              = d.age if d else None
            , diagnostic       = d.diagnostic if d else None
            , address_province = d.address_province if d else None
            , dispense_date    = d.dispense_date if d else date.today()
            , quantity         = it.quantity
            , shift_code       = d.shift_code if d else None
            , payment_code     = d.payment_code if d else None
            , doctor_name      = d.doctor_name if d else None
            , note             = it.note or (d.note if d else None)
            , created_by       = creator
            , created_by_name  = (user_map or {}).get(creator, creator) if creator else None
            , created_datetime = it.created_datetime
        )


    @classmethod
    def record_visit(
        cls
        , session  : Session
        , payload  : DispensingVisitCreate
        , username : str
    ) -> DispensingResponse:
        """Atomically record a patient visit's medicines with FEFO batch deduction."""
        patient = (
            session.query(PATIENT_MODEL)
            .filter(
                PATIENT_MODEL.id == payload.patient_id
                , PATIENT_MODEL.deleted_datetime.is_(None)
            )
            .first()
        )
        if not patient:
            raise HTTPException(
                status_code = status.HTTP_404_NOT_FOUND
                , detail    = "Patient not found."
            )

        resolved_items: List[Tuple[DispensingItemInput, MEDICINE_MODEL]] = []
        has_narcotic = False
        for item_in in payload.items:
            med = cls._resolve_medicine(session, item_in)
            if med.is_narcotic:
                has_narcotic = True
            resolved_items.append((item_in, med))

        if has_narcotic and not (payload.doctor_name or "").strip():
            raise HTTPException(
                status_code = status.HTTP_422_UNPROCESSABLE_ENTITY
                , detail    = "Doctor name is required when dispensing narcotic medicines."
            )

        dispense_date = payload.dispense_date or date.today()
        primary_cat   = resolved_items[0][1].category_code
        record        = PATIENT_DISPENSING_MODEL(
            patient_id         = patient.id
            , dispense_date    = dispense_date
            , department_code  = payload.department_code
            , category_code    = primary_cat
            , patient_name     = patient.full_name
            , age              = patient.age
            , sex              = patient.sex
            , diagnostic       = patient.diagnostic
            , address_province = patient.pob_province
            , shift_code       = payload.shift_code or None
            , payment_code     = payload.payment_code
            , doctor_name      = payload.doctor_name
            , note             = payload.note
            , created_by       = username
        )
        session.add(record)
        session.flush()

        for item_in, med in resolved_items:
            line = PATIENT_DISPENSING_ITEM_MODEL(
                dispensing_id    = record.id
                , medicine_id    = med.id
                , quantity       = item_in.quantity
                , signature_id   = item_in.signature_id
                , signature_note = item_in.signature_note
                , note           = item_in.note or payload.note
                , created_by     = username
            )
            session.add(line)
            session.flush()

            cls._deduct_fefo(
                session              = session
                , department_code    = payload.department_code
                , med                = med
                , quantity           = item_in.quantity
                , dispense_date      = dispense_date
                , dispensing_item_id = line.id
                , note               = line.note
                , username           = username
            )
            cls._sync_stock_usage(
                session           = session
                , stock_date      = dispense_date
                , department_code = payload.department_code
                , medicine_id     = med.id
                , delta_qty       = item_in.quantity
                , username        = username
            )

        session.commit()
        logger.info(
            "DispensingService.record_visit: created with FEFO"
            , f"dispensing_id: {record.id}"
            , f"patient_id: {patient.id}"
            , f"items_count: {len(resolved_items)}"
            , f"username: {username}"
        )
        return cls.get_dispensing(session, record.id)


    @classmethod
    def list_items(
        cls
        , session         : Session
        , start_date      : Optional[date] = None
        , end_date        : Optional[date] = None
        , patient_id      : Optional[UUID] = None
        , medicine_id     : Optional[UUID] = None
        , tabs            : Optional[str]  = None
        , payment_code    : Optional[str]  = None
        , department_code : Optional[str]  = None
        , limit           : int            = 50
        , offset          : int            = 0
    ) -> Tuple[List[DispensingLineResponse], int]:
        query = (
            session.query(PATIENT_DISPENSING_ITEM_MODEL)
            .join(
                PATIENT_DISPENSING_MODEL
                , PATIENT_DISPENSING_ITEM_MODEL.dispensing_id == PATIENT_DISPENSING_MODEL.id
            )
            .join(
                MEDICINE_MODEL
                , PATIENT_DISPENSING_ITEM_MODEL.medicine_id == MEDICINE_MODEL.id
            )
            .options(
                joinedload(PATIENT_DISPENSING_ITEM_MODEL.dispensing)
                , joinedload(PATIENT_DISPENSING_ITEM_MODEL.medicine)
            )
            .filter(
                PATIENT_DISPENSING_ITEM_MODEL.status_code == STATUS_CODE_ENUM.ACTIVE.value
                , PATIENT_DISPENSING_ITEM_MODEL.deleted_datetime.is_(None)
                , PATIENT_DISPENSING_MODEL.status_code == STATUS_CODE_ENUM.ACTIVE.value
                , PATIENT_DISPENSING_MODEL.deleted_datetime.is_(None)
            )
        )
        if start_date:
            query = query.filter(PATIENT_DISPENSING_MODEL.dispense_date >= start_date)
        if end_date:
            query = query.filter(PATIENT_DISPENSING_MODEL.dispense_date <= end_date)
        if patient_id:
            query = query.filter(PATIENT_DISPENSING_MODEL.patient_id == patient_id)
        if medicine_id:
            query = query.filter(PATIENT_DISPENSING_ITEM_MODEL.medicine_id == medicine_id)
        if payment_code:
            query = query.filter(PATIENT_DISPENSING_MODEL.payment_code == payment_code)
        if department_code:
            query = query.filter(PATIENT_DISPENSING_MODEL.department_code == department_code)
        if tabs:
            tab_list   = [t.strip().upper() for t in tabs.split(",") if t.strip()]
            conditions = []
            for tab in tab_list:
                if tab == "NARCOTIC":
                    conditions.append(MEDICINE_MODEL.is_narcotic.is_(True))
                elif tab in ("TABLET", "PILL"):
                    conditions.append(
                        and_(
                            MEDICINE_MODEL.category_code == "TABLET"
                            , MEDICINE_MODEL.is_narcotic.is_(False)
                        )
                    )
                elif tab == "INJECTION":
                    conditions.append(
                        and_(
                            MEDICINE_MODEL.category_code == "INJECTION"
                            , MEDICINE_MODEL.is_narcotic.is_(False)
                        )
                    )
            if conditions:
                query = query.filter(or_(*conditions))

        total = query.count()
        rows  = (
            query.order_by(
                PATIENT_DISPENSING_MODEL.dispense_date.desc()
                , PATIENT_DISPENSING_ITEM_MODEL.created_datetime.desc()
            )
            .offset(offset)
            .limit(limit)
            .all()
        )
        usernames = {r.created_by or (r.dispensing.created_by if r.dispensing else None) for r in rows}
        user_map  = cls._user_fullname_map(session, usernames)
        return [cls._line_to_response(r, user_map) for r in rows], total


    @classmethod
    def delete_item(cls, session: Session, item_id: UUID, username: str) -> None:
        """Soft-delete one dispensing line item and restore all FEFO-deducted stock batches."""
        item = (
            session.query(PATIENT_DISPENSING_ITEM_MODEL)
            .options(joinedload(PATIENT_DISPENSING_ITEM_MODEL.dispensing))
            .filter(
                PATIENT_DISPENSING_ITEM_MODEL.id == item_id
                , PATIENT_DISPENSING_ITEM_MODEL.deleted_datetime.is_(None)
            )
            .with_for_update()
            .first()
        )
        if not item:
            raise HTTPException(
                status_code = status.HTTP_404_NOT_FOUND
                , detail    = "Dispensing line item not found."
            )

        now_utc = utc_now_naive()
        # Restore batch remaining quantities from recorded USAGE movements
        movements = (
            session.query(STOCK_MOVEMENT_MODEL)
            .filter(
                STOCK_MOVEMENT_MODEL.dispensing_item_id == item.id
                , STOCK_MOVEMENT_MODEL.movement_type == "USAGE"
                , STOCK_MOVEMENT_MODEL.deleted_datetime.is_(None)
            )
            .with_for_update()
            .all()
        )
        for mv in movements:
            if mv.batch_id:
                batch = (
                    session.query(STOCK_BATCH_MODEL)
                    .filter(STOCK_BATCH_MODEL.id == mv.batch_id)
                    .with_for_update()
                    .first()
                )
                if batch:
                    batch.remaining_qty    = (batch.remaining_qty or Decimal("0")) + (mv.quantity or Decimal("0"))
                    batch.updated_by       = username
                    batch.updated_datetime = now_utc
            mv.status_code      = STATUS_CODE_ENUM.DELETED.value
            mv.deleted_by       = username
            mv.deleted_datetime = now_utc

        if item.dispensing:
            cls._sync_stock_usage(
                session           = session
                , stock_date      = item.dispensing.dispense_date
                , department_code = item.dispensing.department_code
                , medicine_id     = item.medicine_id
                , delta_qty       = -(item.quantity or Decimal("0"))
                , username        = username
            )

        item.status_code      = STATUS_CODE_ENUM.DELETED.value
        item.deleted_by       = username
        item.deleted_datetime = now_utc
        session.flush()

        # If parent dispensing has no remaining active items, soft-delete parent as well
        if item.dispensing:
            active_siblings = (
                session.query(PATIENT_DISPENSING_ITEM_MODEL.id)
                .filter(
                    PATIENT_DISPENSING_ITEM_MODEL.dispensing_id == item.dispensing_id
                    , PATIENT_DISPENSING_ITEM_MODEL.deleted_datetime.is_(None)
                )
                .count()
            )
            if active_siblings == 0:
                item.dispensing.status_code      = STATUS_CODE_ENUM.DELETED.value
                item.dispensing.deleted_by       = username
                item.dispensing.deleted_datetime = now_utc

        session.commit()
        logger.info(
            "DispensingService.delete_item: soft-deleted and restored stock"
            , f"item_id: {item_id}"
            , f"movements_restored: {len(movements)}"
            , f"username: {username}"
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
            , shift_code       = payload.shift_code
            , payment_code     = payload.payment_code
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
        , limit           : int            = 100
        , offset          : int            = 0
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

        rows = (
            query.order_by(
                PATIENT_DISPENSING_MODEL.dispense_date.desc()
                , PATIENT_DISPENSING_MODEL.patient_no
            )
            .offset(offset)
            .limit(limit)
            .all()
        )
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
        record.updated_datetime = utc_now_naive()

        if payload.items is not None:
            old_items = (
                session.query(PATIENT_DISPENSING_ITEM_MODEL)
                .filter(
                    PATIENT_DISPENSING_ITEM_MODEL.dispensing_id == record.id
                    , PATIENT_DISPENSING_ITEM_MODEL.deleted_datetime.is_(None)
                )
                .all()
            )
            for old_item in old_items:
                cls._sync_stock_usage(
                    session           = session
                    , stock_date      = record.dispense_date
                    , department_code = record.department_code
                    , medicine_id     = old_item.medicine_id
                    , delta_qty       = -(old_item.quantity or Decimal("0"))
                    , username        = username
                )
                session.delete(old_item)

            for item_in in payload.items:
                med = cls._resolve_medicine(session, item_in)
                session.add(
                    PATIENT_DISPENSING_ITEM_MODEL(
                        dispensing_id    = record.id
                        , medicine_id    = med.id
                        , quantity       = item_in.quantity
                        , signature_id   = item_in.signature_id
                        , signature_note = item_in.signature_note
                        , note           = item_in.note
                        , created_by     = username
                    )
                )
                cls._sync_stock_usage(
                    session           = session
                    , stock_date      = record.dispense_date
                    , department_code = record.department_code
                    , medicine_id     = med.id
                    , delta_qty       = item_in.quantity
                    , username        = username
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
            .options(joinedload(PATIENT_DISPENSING_MODEL.items))
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

        now_utc = utc_now_naive()
        for item in record.items:
            if item.deleted_datetime is None:
                cls._sync_stock_usage(
                    session           = session
                    , stock_date      = record.dispense_date
                    , department_code = record.department_code
                    , medicine_id     = item.medicine_id
                    , delta_qty       = -(item.quantity or Decimal("0"))
                    , username        = username
                )
                item.status_code      = STATUS_CODE_ENUM.DELETED.value
                item.deleted_by       = username
                item.deleted_datetime = now_utc

        record.status_code      = STATUS_CODE_ENUM.DELETED.value
        record.deleted_by       = username
        record.deleted_datetime = now_utc
        session.commit()
        logger.info(
            "DispensingService.delete_dispensing: soft-deleted"
            , f"dispensing_id: {dispensing_id}"
            , f"username: {username}"
        )
