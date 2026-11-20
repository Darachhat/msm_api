from datetime import date, datetime, timedelta
from typing   import List, Optional

from fastapi        import HTTPException, status
from sqlalchemy.orm import Session, joinedload

from app.core.enum              import STATUS_CODE_ENUM
from app.core.log               import logger
from app.models.base_data_model import MEDICINE_MODEL
from app.models.data_model      import STOCK_BATCH_MODEL, STOCK_LEDGER_MODEL
from app.schemas.stock_schema   import (
    StockBatchCreate
    , StockBatchResponse
    , StockLedgerBatchUpsert
    , StockLedgerResponse
    , StockLedgerUpsertItem
)


class StockService:

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
                ledger.updated_datetime = datetime.utcnow()
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
        , category_code   : Optional[str] = None
        , department_code : Optional[str] = None
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

        rows = query.order_by(
            STOCK_LEDGER_MODEL.stock_date.desc()
            , MEDICINE_MODEL.sort_order
        ).all()
        return [cls._to_response(r) for r in rows]


    @staticmethod
    def _batch_to_response(b: STOCK_BATCH_MODEL) -> StockBatchResponse:
        return StockBatchResponse(
            id                = b.id
            , department_code = b.department_code
            , medicine_id     = b.medicine_id
            , medicine_code   = b.medicine.code if b.medicine else None
            , medicine_name   = b.medicine.name if b.medicine else None
            , category_code   = b.medicine.category_code if b.medicine else None
            , is_narcotic     = b.medicine.is_narcotic if b.medicine else None
            , batch_no        = b.batch_no
            , total_qty       = b.total_qty
            , remaining_qty   = b.remaining_qty
            , input_date      = b.input_date
            , expire_date     = b.expire_date
            , note            = b.note
        )


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

        in_date = payload.input_date or date.today()
        batch   = STOCK_BATCH_MODEL(
            department_code = payload.department_code
            , medicine_id   = med.id
            , batch_no      = payload.batch_no
            , total_qty     = payload.total_qty
            , remaining_qty = payload.total_qty
            , input_date    = in_date
            , expire_date   = payload.expire_date
            , note          = payload.note
            , created_by    = username
        )
        session.add(batch)

        # Also reflect added_qty in daily stock_ledger
        ledger = (
            session.query(STOCK_LEDGER_MODEL)
            .filter(
                STOCK_LEDGER_MODEL.stock_date == in_date
                , STOCK_LEDGER_MODEL.department_code == payload.department_code
                , STOCK_LEDGER_MODEL.medicine_id == med.id
            )
            .first()
        )
        if not ledger:
            ledger = STOCK_LEDGER_MODEL(
                stock_date        = in_date
                , department_code = payload.department_code
                , medicine_id     = med.id
                , opening_qty     = 0
                , added_qty       = payload.total_qty
                , used_qty        = 0
                , remaining_qty   = payload.total_qty
                , created_by      = username
            )
            session.add(ledger)
        else:
            ledger.added_qty        = (ledger.added_qty or 0) + payload.total_qty
            ledger.remaining_qty    = (ledger.opening_qty or 0) + ledger.added_qty - (ledger.used_qty or 0)
            ledger.updated_by       = username
            ledger.updated_datetime = datetime.utcnow()

        session.commit()
        session.refresh(batch)
        batch.medicine = med
        logger.info(
            "StockService.insert_stock_batch: inserted"
            , f"batch_id: {batch.id}"
            , f"department_code: {payload.department_code}"
            , f"medicine_code: {med.code}"
            , f"total_qty: {payload.total_qty}"
            , f"username: {username}"
        )
        return cls._batch_to_response(batch)


    @classmethod
    def list_stock_batches(
        cls
        , session              : Session
        , tab                  : Optional[str] = None  # TABLET | INJECTION | NARCOTIC
        , department_code      : Optional[str] = None
        , expiring_within_days : Optional[int] = None
    ) -> List[StockBatchResponse]:
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
        if tab == "NARCOTIC":
            query = query.filter(MEDICINE_MODEL.is_narcotic.is_(True))
        elif tab == "TABLET":
            query = query.filter(MEDICINE_MODEL.category_code == "TABLET")
        elif tab == "INJECTION":
            query = query.filter(
                MEDICINE_MODEL.category_code == "INJECTION"
                , MEDICINE_MODEL.is_narcotic.is_(False)
            )
        if expiring_within_days is not None:
            cutoff = date.today() + timedelta(days = expiring_within_days)
            query  = query.filter(
                STOCK_BATCH_MODEL.expire_date.is_not(None)
                , STOCK_BATCH_MODEL.expire_date <= cutoff
            )

        rows = query.order_by(
            STOCK_BATCH_MODEL.expire_date.asc().nullslast()
            , STOCK_BATCH_MODEL.input_date.desc()
        ).all()
        return [cls._batch_to_response(r) for r in rows]
