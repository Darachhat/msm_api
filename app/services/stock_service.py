from datetime import date, timedelta
from decimal  import Decimal
from typing   import Dict, List, Optional, Tuple
from uuid     import UUID

from fastapi        import HTTPException, status
from sqlalchemy     import or_
from sqlalchemy.orm import Session, joinedload

from app.core.constants         import utc_now_naive
from app.core.enum              import STATUS_CODE_ENUM
from app.core.log               import logger
from app.models.base_data_model import MEDICINE_MODEL
from app.models.data_model      import (
    PATIENT_DISPENSING_ITEM_MODEL
    , STOCK_BATCH_MODEL
    , STOCK_LEDGER_MODEL
    , STOCK_MOVEMENT_MODEL
    , USER_MODEL
)
from app.schemas.stock_schema   import (
    StockBatchBulkCreate
    , StockBatchCreate
    , StockBatchResponse
    , StockBatchUpdate
    , StockLedgerBatchUpsert
    , StockLedgerResponse
    , StockLedgerUpsertItem
    , StockMovementResponse
    , StockWriteOffCreate
)

_WRITEOFF_TYPES = frozenset({"EXPIRED", "DAMAGED", "ADJUSTMENT"})


class StockService:

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
    def _resolve_medicine(session: Session, item: StockLedgerUpsertItem) -> MEDICINE_MODEL:
        med = None
        if item.medicine_id:
            med = session.query(MEDICINE_MODEL).filter(MEDICINE_MODEL.id == item.medicine_id).first()
        elif item.medicine_code:
            med = session.query(MEDICINE_MODEL).filter(MEDICINE_MODEL.code == item.medicine_code).first()
        if not med:
            logger.warn(
                "StockService._resolve_medicine: medicine not found"
                , f"medicine_id: {item.medicine_id}"
                , f"medicine_code: {item.medicine_code}"
            )
            raise HTTPException(
                status_code = status.HTTP_404_NOT_FOUND
                , detail    = f"Medicine not found (id={item.medicine_id}, code={item.medicine_code})."
            )
        return med


    @staticmethod
    def _to_response(row: STOCK_LEDGER_MODEL) -> StockLedgerResponse:
        return StockLedgerResponse(
            id                = row.id
            , stock_date      = row.stock_date
            , department_code = row.department_code
            , medicine_id     = row.medicine_id
            , medicine_code   = row.medicine.code if row.medicine else None
            , medicine_name   = row.medicine.name if row.medicine else None
            , form_code       = row.medicine.form_code if row.medicine else None
            , dosage          = row.medicine.dosage if row.medicine else None
            , opening_qty     = row.opening_qty
            , added_qty       = row.added_qty
            , used_qty        = row.used_qty
            , remaining_qty   = row.remaining_qty
            , requested_qty   = row.requested_qty
            , supplied_qty    = row.supplied_qty
            , note            = row.note
        )


    @classmethod
    def batch_upsert(
        cls
        , session  : Session
        , payload  : StockLedgerBatchUpsert
        , username : str
    ) -> List[StockLedgerResponse]:
        results: List[STOCK_LEDGER_MODEL] = []
        for item in payload.items:
            med       = cls._resolve_medicine(session, item)
            remaining = (
                item.remaining_qty
                if item.remaining_qty is not None
                else (item.opening_qty + item.added_qty - item.used_qty)
            )
            ledger = (
                session.query(STOCK_LEDGER_MODEL)
                .filter(
                    STOCK_LEDGER_MODEL.stock_date == payload.stock_date
                    , STOCK_LEDGER_MODEL.department_code == payload.department_code
                    , STOCK_LEDGER_MODEL.medicine_id == med.id
                )
                .first()
            )
            if not ledger:
                ledger = STOCK_LEDGER_MODEL(
                    stock_date        = payload.stock_date
                    , department_code = payload.department_code
                    , medicine_id     = med.id
                    , opening_qty     = item.opening_qty
                    , added_qty       = item.added_qty
                    , used_qty        = item.used_qty
                    , remaining_qty   = remaining
                    , requested_qty   = item.requested_qty
                    , supplied_qty    = item.supplied_qty
                    , note            = item.note
                    , created_by      = username
                )
                session.add(ledger)
            else:
                ledger.opening_qty      = item.opening_qty
                ledger.added_qty        = item.added_qty
                ledger.used_qty         = item.used_qty
                ledger.remaining_qty    = remaining
                ledger.requested_qty    = item.requested_qty
                ledger.supplied_qty     = item.supplied_qty
                ledger.note             = item.note
                ledger.updated_by       = username
                ledger.updated_datetime = utc_now_naive()
            results.append(ledger)

        session.commit()
        for r in results:
            session.refresh(r)
        logger.info(
            "StockService.batch_upsert: completed"
            , f"stock_date: {payload.stock_date}"
            , f"department_code: {payload.department_code}"
            , f"items_count: {len(results)}"
            , f"username: {username}"
        )
        return [cls._to_response(r) for r in results]


    @classmethod
    def list_stock(
        cls
        , session         : Session
        , stock_date      : Optional[date] = None
        , start_date      : Optional[date] = None
        , end_date        : Optional[date] = None
        , category_code   : Optional[str]  = None
        , department_code : Optional[str]  = None
        , limit           : int            = 100
        , offset          : int            = 0
    ) -> List[StockLedgerResponse]:
        query = (
            session.query(STOCK_LEDGER_MODEL)
            .join(MEDICINE_MODEL, STOCK_LEDGER_MODEL.medicine_id == MEDICINE_MODEL.id)
            .options(joinedload(STOCK_LEDGER_MODEL.medicine))
            .filter(
                STOCK_LEDGER_MODEL.status_code == STATUS_CODE_ENUM.ACTIVE.value
                , STOCK_LEDGER_MODEL.deleted_datetime.is_(None)
            )
        )
        if stock_date:
            query = query.filter(STOCK_LEDGER_MODEL.stock_date == stock_date)
        if start_date:
            query = query.filter(STOCK_LEDGER_MODEL.stock_date >= start_date)
        if end_date:
            query = query.filter(STOCK_LEDGER_MODEL.stock_date <= end_date)
        if category_code:
            query = query.filter(MEDICINE_MODEL.category_code == category_code)
        if department_code:
            query = query.filter(STOCK_LEDGER_MODEL.department_code == department_code)

        rows = (
            query.order_by(
                STOCK_LEDGER_MODEL.stock_date.desc()
                , MEDICINE_MODEL.sort_order
            )
            .offset(offset)
            .limit(limit)
            .all()
        )
        return [cls._to_response(r) for r in rows]


    @staticmethod
    def _batch_to_response(
        b         : STOCK_BATCH_MODEL
        , user_map: Optional[Dict[str, str]] = None
    ) -> StockBatchResponse:
        return StockBatchResponse(
            id                 = b.id
            , department_code  = b.department_code
            , medicine_id      = b.medicine_id
            , medicine_code    = b.medicine.code if b.medicine else None
            , medicine_name    = b.medicine.name if b.medicine else None
            , form_code        = b.medicine.form_code if b.medicine else None
            , dosage           = b.medicine.dosage if b.medicine else None
            , category_code    = b.medicine.category_code if b.medicine else None
            , is_narcotic      = b.medicine.is_narcotic if b.medicine else None
            , batch_no         = b.batch_no
            , source           = b.source
            , total_qty        = b.total_qty
            , remaining_qty    = b.remaining_qty
            , input_date       = b.input_date
            , expire_date      = b.expire_date
            , note             = b.note
            , created_by       = b.created_by
            , created_by_name  = (user_map or {}).get(b.created_by, b.created_by) if b.created_by else None
            , created_datetime = b.created_datetime
        )


    @staticmethod
    def _add_batch_record(
        session           : Session
        , department_code : str
        , med             : MEDICINE_MODEL
        , total_qty       : Decimal
        , input_date      : Optional[date]
        , expire_date     : Optional[date]
        , batch_no        : Optional[str]
        , source          : Optional[str]
        , note            : Optional[str]
        , username        : str
    ) -> STOCK_BATCH_MODEL:
        in_date = input_date or date.today()
        if expire_date is not None and expire_date <= in_date:
            raise HTTPException(
                status_code = status.HTTP_422_UNPROCESSABLE_ENTITY
                , detail    = "Expiry date must be after the input date."
            )
        batch = STOCK_BATCH_MODEL(
            department_code = department_code
            , medicine_id   = med.id
            , batch_no      = batch_no
            , source        = source
            , total_qty     = total_qty
            , remaining_qty = total_qty
            , input_date    = in_date
            , expire_date   = expire_date
            , note          = note
            , created_by    = username
        )
        session.add(batch)
        session.flush()

        session.add(
            STOCK_MOVEMENT_MODEL(
                department_code = department_code
                , medicine_id   = med.id
                , batch_id      = batch.id
                , movement_type = "IN"
                , movement_date = in_date
                , quantity      = total_qty
                , note          = note
                , created_by    = username
            )
        )

        # Also reflect added_qty in daily stock_ledger
        ledger = (
            session.query(STOCK_LEDGER_MODEL)
            .filter(
                STOCK_LEDGER_MODEL.stock_date == in_date
                , STOCK_LEDGER_MODEL.department_code == department_code
                , STOCK_LEDGER_MODEL.medicine_id == med.id
            )
            .first()
        )
        if not ledger:
            ledger = STOCK_LEDGER_MODEL(
                stock_date        = in_date
                , department_code = department_code
                , medicine_id     = med.id
                , opening_qty     = Decimal("0")
                , added_qty       = total_qty
                , used_qty        = Decimal("0")
                , remaining_qty   = total_qty
                , created_by      = username
            )
            session.add(ledger)
        else:
            ledger.added_qty        = (ledger.added_qty or Decimal("0")) + total_qty
            ledger.remaining_qty    = (ledger.opening_qty or Decimal("0")) + ledger.added_qty - (ledger.used_qty or Decimal("0"))
            ledger.updated_by       = username
            ledger.updated_datetime = utc_now_naive()

        batch.medicine = med
        return batch


    @classmethod
    def insert_stock_batch(
        cls
        , session  : Session
        , payload  : StockBatchCreate
        , username : str
    ) -> StockBatchResponse:
        med = None
        if payload.medicine_id:
            med = session.query(MEDICINE_MODEL).filter(MEDICINE_MODEL.id == payload.medicine_id).first()
        elif payload.medicine_code:
            med = session.query(MEDICINE_MODEL).filter(MEDICINE_MODEL.code == payload.medicine_code).first()
        if not med:
            logger.warn(
                "StockService.insert_stock_batch: medicine not found"
                , f"medicine_id: {payload.medicine_id}"
                , f"medicine_code: {payload.medicine_code}"
            )
            raise HTTPException(
                status_code = status.HTTP_404_NOT_FOUND
                , detail    = "Medicine not found."
            )

        batch = cls._add_batch_record(
            session           = session
            , department_code = payload.department_code
            , med             = med
            , total_qty       = payload.total_qty
            , input_date      = payload.input_date
            , expire_date     = payload.expire_date
            , batch_no        = payload.batch_no
            , source          = payload.source
            , note            = payload.note
            , username        = username
        )
        session.commit()
        session.refresh(batch)
        batch.medicine = med
        user_map = cls._user_fullname_map(session, {username})
        logger.info(
            "StockService.insert_stock_batch: inserted"
            , f"batch_id: {batch.id}"
            , f"department_code: {payload.department_code}"
            , f"medicine_code: {med.code}"
            , f"total_qty: {payload.total_qty}"
            , f"username: {username}"
        )
        return cls._batch_to_response(batch, user_map)


    @classmethod
    def bulk_insert_batches(
        cls
        , session  : Session
        , payload  : StockBatchBulkCreate
        , username : str
    ) -> List[StockBatchResponse]:
        created: List[STOCK_BATCH_MODEL] = []
        for item in payload.items:
            med = None
            if item.medicine_id:
                med = session.query(MEDICINE_MODEL).filter(MEDICINE_MODEL.id == item.medicine_id).first()
            elif item.medicine_code:
                med = session.query(MEDICINE_MODEL).filter(MEDICINE_MODEL.code == item.medicine_code).first()
            if not med:
                raise HTTPException(
                    status_code = status.HTTP_404_NOT_FOUND
                    , detail    = f"Medicine not found (id={item.medicine_id}, code={item.medicine_code})."
                )
            batch = cls._add_batch_record(
                session           = session
                , department_code = payload.department_code
                , med             = med
                , total_qty       = item.total_qty
                , input_date      = item.input_date
                , expire_date     = item.expire_date
                , batch_no        = item.batch_no
                , source          = item.source
                , note            = item.note
                , username        = username
            )
            created.append(batch)

        session.commit()
        user_map = cls._user_fullname_map(session, {username})
        for b in created:
            session.refresh(b)
        logger.info(
            "StockService.bulk_insert_batches: inserted"
            , f"count: {len(created)}"
            , f"department_code: {payload.department_code}"
            , f"username: {username}"
        )
        return [cls._batch_to_response(b, user_map) for b in created]


    @classmethod
    def update_batch(
        cls
        , session  : Session
        , batch_id : UUID
        , payload  : StockBatchUpdate
        , username : str
    ) -> StockBatchResponse:
        batch = (
            session.query(STOCK_BATCH_MODEL)
            .options(joinedload(STOCK_BATCH_MODEL.medicine))
            .filter(
                STOCK_BATCH_MODEL.id == batch_id
                , STOCK_BATCH_MODEL.deleted_datetime.is_(None)
            )
            .with_for_update()
            .first()
        )
        if not batch:
            raise HTTPException(
                status_code = status.HTTP_404_NOT_FOUND
                , detail    = "Stock batch not found."
            )

        updates  = payload.model_dump(exclude_unset = True)
        new_in   = updates.get("input_date", batch.input_date)
        new_exp  = updates.get("expire_date", batch.expire_date)
        if new_exp is not None and new_in is not None and new_exp <= new_in:
            raise HTTPException(
                status_code = status.HTTP_422_UNPROCESSABLE_ENTITY
                , detail    = "Expiry date must be after the input date."
            )

        if "total_qty" in updates and updates["total_qty"] is not None:
            delta     = updates["total_qty"] - (batch.total_qty or Decimal("0"))
            new_rem   = (batch.remaining_qty or Decimal("0")) + delta
            if new_rem < 0:
                raise HTTPException(
                    status_code = status.HTTP_400_BAD_REQUEST
                    , detail    = "New total quantity cannot be less than the quantity already used or written off."
                )
            batch.total_qty     = updates["total_qty"]
            batch.remaining_qty = new_rem

        for field in ("input_date", "expire_date", "batch_no", "source", "note"):
            if field in updates:
                setattr(batch, field, updates[field])

        now_utc                = utc_now_naive()
        batch.updated_by       = username
        batch.updated_datetime = now_utc

        # Keep the initial IN movement row synchronized
        in_mv = (
            session.query(STOCK_MOVEMENT_MODEL)
            .filter(
                STOCK_MOVEMENT_MODEL.batch_id == batch.id
                , STOCK_MOVEMENT_MODEL.movement_type == "IN"
                , STOCK_MOVEMENT_MODEL.deleted_datetime.is_(None)
            )
            .first()
        )
        if in_mv:
            in_mv.quantity         = batch.total_qty
            in_mv.movement_date    = batch.input_date
            in_mv.note             = batch.note
            in_mv.updated_by       = username
            in_mv.updated_datetime = now_utc

        session.commit()
        session.refresh(batch)
        user_map = cls._user_fullname_map(session, {batch.created_by})
        return cls._batch_to_response(batch, user_map)


    @classmethod
    def delete_batch(cls, session: Session, batch_id: UUID, username: str) -> None:
        batch = (
            session.query(STOCK_BATCH_MODEL)
            .filter(
                STOCK_BATCH_MODEL.id == batch_id
                , STOCK_BATCH_MODEL.deleted_datetime.is_(None)
            )
            .with_for_update()
            .first()
        )
        if not batch:
            raise HTTPException(
                status_code = status.HTTP_404_NOT_FOUND
                , detail    = "Stock batch not found."
            )
        if (batch.remaining_qty or Decimal("0")) < (batch.total_qty or Decimal("0")):
            raise HTTPException(
                status_code = status.HTTP_400_BAD_REQUEST
                , detail    = "Cannot delete a batch that already has usage or write-offs."
            )

        now_utc                = utc_now_naive()
        batch.status_code      = STATUS_CODE_ENUM.DELETED.value
        batch.deleted_by       = username
        batch.deleted_datetime = now_utc

        session.query(STOCK_MOVEMENT_MODEL).filter(
            STOCK_MOVEMENT_MODEL.batch_id == batch.id
            , STOCK_MOVEMENT_MODEL.deleted_datetime.is_(None)
        ).update({
            "status_code"        : STATUS_CODE_ENUM.DELETED.value
            , "deleted_by"       : username
            , "deleted_datetime" : now_utc
        })
        session.commit()


    @classmethod
    def create_writeoff(
        cls
        , session  : Session
        , payload  : StockWriteOffCreate
        , username : str
    ) -> StockMovementResponse:
        mv_type = payload.movement_type.strip().upper()
        if mv_type not in _WRITEOFF_TYPES:
            raise HTTPException(
                status_code = status.HTTP_422_UNPROCESSABLE_ENTITY
                , detail    = f"Invalid write-off movement_type '{mv_type}'. Must be one of: EXPIRED, DAMAGED, ADJUSTMENT."
            )

        batch = (
            session.query(STOCK_BATCH_MODEL)
            .filter(
                STOCK_BATCH_MODEL.id == payload.batch_id
                , STOCK_BATCH_MODEL.status_code == STATUS_CODE_ENUM.ACTIVE.value
                , STOCK_BATCH_MODEL.deleted_datetime.is_(None)
            )
            .with_for_update()
            .first()
        )
        if not batch:
            raise HTTPException(
                status_code = status.HTTP_404_NOT_FOUND
                , detail    = "Stock batch not found."
            )
        if (batch.remaining_qty or Decimal("0")) < payload.quantity:
            raise HTTPException(
                status_code = status.HTTP_400_BAD_REQUEST
                , detail    = f"Insufficient remaining quantity in batch (available: {batch.remaining_qty})."
            )

        now_utc                = utc_now_naive()
        batch.remaining_qty    = (batch.remaining_qty or Decimal("0")) - payload.quantity
        batch.updated_by       = username
        batch.updated_datetime = now_utc

        mv = STOCK_MOVEMENT_MODEL(
            department_code = batch.department_code
            , medicine_id   = batch.medicine_id
            , batch_id      = batch.id
            , movement_type = mv_type
            , movement_date = payload.movement_date or date.today()
            , quantity      = payload.quantity
            , note          = payload.note
            , created_by    = username
        )
        session.add(mv)
        session.commit()
        session.refresh(mv)
        user_map = cls._user_fullname_map(session, {username})
        return StockMovementResponse(
            id                 = mv.id
            , department_code  = mv.department_code
            , medicine_id      = mv.medicine_id
            , batch_id         = mv.batch_id
            , batch_no         = batch.batch_no
            , batch_source     = batch.source
            , movement_type    = mv.movement_type
            , movement_date    = mv.movement_date
            , quantity         = mv.quantity
            , note             = mv.note
            , created_by       = mv.created_by
            , created_by_name  = user_map.get(username, username)
            , created_datetime = mv.created_datetime
        )


    @classmethod
    def delete_writeoff(cls, session: Session, movement_id: UUID, username: str) -> None:
        mv = (
            session.query(STOCK_MOVEMENT_MODEL)
            .filter(
                STOCK_MOVEMENT_MODEL.id == movement_id
                , STOCK_MOVEMENT_MODEL.movement_type.in_(list(_WRITEOFF_TYPES))
                , STOCK_MOVEMENT_MODEL.deleted_datetime.is_(None)
            )
            .with_for_update()
            .first()
        )
        if not mv:
            raise HTTPException(
                status_code = status.HTTP_404_NOT_FOUND
                , detail    = "Write-off record not found."
            )

        now_utc = utc_now_naive()
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
        session.commit()


    @classmethod
    def list_movements(
        cls
        , session         : Session
        , medicine_id     : Optional[UUID] = None
        , department_code : Optional[str]  = None
        , limit           : int            = 100
    ) -> List[StockMovementResponse]:
        query = (
            session.query(STOCK_MOVEMENT_MODEL)
            .options(
                joinedload(STOCK_MOVEMENT_MODEL.batch)
                , joinedload(STOCK_MOVEMENT_MODEL.dispensing_item).joinedload(PATIENT_DISPENSING_ITEM_MODEL.dispensing)
            )
            .filter(
                STOCK_MOVEMENT_MODEL.status_code == STATUS_CODE_ENUM.ACTIVE.value
                , STOCK_MOVEMENT_MODEL.deleted_datetime.is_(None)
            )
        )
        if medicine_id:
            query = query.filter(STOCK_MOVEMENT_MODEL.medicine_id == medicine_id)
        if department_code:
            query = query.filter(STOCK_MOVEMENT_MODEL.department_code == department_code)

        rows = (
            query.order_by(
                STOCK_MOVEMENT_MODEL.movement_date.desc()
                , STOCK_MOVEMENT_MODEL.created_datetime.desc()
            )
            .limit(limit)
            .all()
        )
        user_map = cls._user_fullname_map(session, {r.created_by for r in rows})
        out: List[StockMovementResponse] = []
        for r in rows:
            p_name = None
            if r.dispensing_item and r.dispensing_item.dispensing:
                p_name = r.dispensing_item.dispensing.patient_name
            out.append(
                StockMovementResponse(
                    id                 = r.id
                    , department_code  = r.department_code
                    , medicine_id      = r.medicine_id
                    , batch_id         = r.batch_id
                    , batch_no         = r.batch.batch_no if r.batch else None
                    , batch_source     = r.batch.source if r.batch else None
                    , patient_name     = p_name
                    , movement_type    = r.movement_type
                    , movement_date    = r.movement_date
                    , quantity         = r.quantity
                    , note             = r.note
                    , created_by       = r.created_by
                    , created_by_name  = user_map.get(r.created_by, r.created_by) if r.created_by else None
                    , created_datetime = r.created_datetime
                )
            )
        return out


    @classmethod
    def list_stock_batches(
        cls
        , session              : Session
        , tab                  : Optional[str]  = None
        , medicine_id          : Optional[UUID] = None
        , availability         : Optional[str]  = None  # AVAILABLE | EXPIRING | EXPIRED
        , department_code      : Optional[str]  = None
        , expiring_within_days : Optional[int]  = None
        , limit                : int            = 100
        , offset               : int            = 0
    ) -> Tuple[List[StockBatchResponse], int]:
        today = date.today()
        query = (
            session.query(STOCK_BATCH_MODEL)
            .join(MEDICINE_MODEL, STOCK_BATCH_MODEL.medicine_id == MEDICINE_MODEL.id)
            .options(joinedload(STOCK_BATCH_MODEL.medicine))
            .filter(
                STOCK_BATCH_MODEL.status_code == STATUS_CODE_ENUM.ACTIVE.value
                , STOCK_BATCH_MODEL.deleted_datetime.is_(None)
            )
        )
        if department_code:
            query = query.filter(STOCK_BATCH_MODEL.department_code == department_code)
        if medicine_id:
            query = query.filter(STOCK_BATCH_MODEL.medicine_id == medicine_id)
        if tab == "NARCOTIC":
            query = query.filter(MEDICINE_MODEL.is_narcotic.is_(True))
        elif tab == "TABLET":
            query = query.filter(
                MEDICINE_MODEL.category_code == "TABLET"
                , MEDICINE_MODEL.is_narcotic.is_(False)
            )
        elif tab == "INJECTION":
            query = query.filter(
                MEDICINE_MODEL.category_code == "INJECTION"
                , MEDICINE_MODEL.is_narcotic.is_(False)
            )

        avail = (availability or "").strip().upper()
        if avail == "AVAILABLE":
            query = query.filter(
                STOCK_BATCH_MODEL.remaining_qty > 0
                , or_(
                    STOCK_BATCH_MODEL.expire_date.is_(None)
                    , STOCK_BATCH_MODEL.expire_date >= today
                )
            )
        elif avail == "EXPIRING":
            cutoff = today + timedelta(days = expiring_within_days or 90)
            query  = query.filter(
                STOCK_BATCH_MODEL.remaining_qty > 0
                , STOCK_BATCH_MODEL.expire_date.is_not(None)
                , STOCK_BATCH_MODEL.expire_date >= today
                , STOCK_BATCH_MODEL.expire_date <= cutoff
            )
        elif avail == "EXPIRED":
            query = query.filter(
                STOCK_BATCH_MODEL.remaining_qty > 0
                , STOCK_BATCH_MODEL.expire_date.is_not(None)
                , STOCK_BATCH_MODEL.expire_date < today
            )
        elif expiring_within_days is not None:
            cutoff = today + timedelta(days = expiring_within_days)
            query  = query.filter(
                STOCK_BATCH_MODEL.expire_date.is_not(None)
                , STOCK_BATCH_MODEL.expire_date <= cutoff
            )

        total = query.count()
        rows  = (
            query.order_by(
                STOCK_BATCH_MODEL.expire_date.asc().nullslast()
                , STOCK_BATCH_MODEL.input_date.desc()
            )
            .offset(offset)
            .limit(limit)
            .all()
        )
        user_map = cls._user_fullname_map(session, {r.created_by for r in rows})
        return [cls._batch_to_response(r, user_map) for r in rows], total
