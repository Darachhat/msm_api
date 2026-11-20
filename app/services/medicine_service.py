from datetime import date, timedelta
from decimal  import Decimal
import re
from typing   import Dict, List, Optional
from uuid     import UUID, uuid4

from fastapi        import HTTPException, status
from sqlalchemy     import and_, or_
from sqlalchemy.orm import Session, joinedload

from app.core.constants         import utc_now_naive
from app.core.enum              import STATUS_CODE_ENUM
from app.core.log               import logger
from app.models.base_data_model import (
    DEPARTMENT_MODEL
    , MEDICINE_CATEGORY_MODEL
    , MEDICINE_FORM_MODEL
    , MEDICINE_MODEL
)
from app.models.data_model      import (
    PATIENT_DISPENSING_ITEM_MODEL
    , STOCK_BATCH_MODEL
    , STOCK_MOVEMENT_MODEL
)
from app.schemas.medicine_schema import (
    MedicineCreate
    , MedicineResponse
    , MedicineStockSummary
    , MedicineUpdate
)


def _generate_medicine_code(name: str) -> str:
    slug = re.sub(r"[^A-Z0-9]+", "_", name.upper()).strip("_")[:40] or "MED"
    return f"{slug}_{uuid4().hex[:6].upper()}"


def _apply_tabs_filter(query, tabs: Optional[str]):
    """Filter MEDICINE_MODEL query by comma-separated tabs (TABLET, INJECTION, NARCOTIC)."""
    if not tabs:
        return query
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
    return query


class MedicineService:

    @staticmethod
    def _compute_stock_map(
        session           : Session
        , medicine_ids    : List[UUID]
        , department_code : Optional[str] = None
        , warn_days       : int           = 90
    ) -> Dict[UUID, MedicineStockSummary]:
        if not medicine_ids:
            return {}
        today  = date.today()
        cutoff = today + timedelta(days = warn_days)

        batch_q = session.query(STOCK_BATCH_MODEL).filter(
            STOCK_BATCH_MODEL.medicine_id.in_(medicine_ids)
            , STOCK_BATCH_MODEL.status_code == STATUS_CODE_ENUM.ACTIVE.value
            , STOCK_BATCH_MODEL.deleted_datetime.is_(None)
            , STOCK_BATCH_MODEL.remaining_qty > 0
        )
        if department_code:
            batch_q = batch_q.filter(STOCK_BATCH_MODEL.department_code == department_code)

        agg: Dict[UUID, dict] = {}
        for b in batch_q.all():
            rem = b.remaining_qty or Decimal("0")
            entry = agg.setdefault(
                b.medicine_id
                , {
                    "balance"          : Decimal("0")
                    , "usable"         : Decimal("0")
                    , "expired_qty"    : Decimal("0")
                    , "expiring_qty"   : Decimal("0")
                    , "nearest_expiry" : None
                    , "batch_count"    : 0
                }
            )
            entry["balance"]     += rem
            entry["batch_count"] += 1
            if b.expire_date is not None and b.expire_date < today:
                entry["expired_qty"] += rem
            else:
                entry["usable"] += rem
                if b.expire_date is not None:
                    if b.expire_date <= cutoff:
                        entry["expiring_qty"] += rem
                    if entry["nearest_expiry"] is None or b.expire_date < entry["nearest_expiry"]:
                        entry["nearest_expiry"] = b.expire_date

        result: Dict[UUID, MedicineStockSummary] = {}
        for mid, entry in agg.items():
            result[mid] = MedicineStockSummary(
                balance          = entry["balance"]
                , usable         = entry["usable"]
                , expired_qty    = entry["expired_qty"]
                , expiring_qty   = entry["expiring_qty"]
                , nearest_expiry = entry["nearest_expiry"]
                , batch_count    = entry["batch_count"]
            )
        return result


    @staticmethod
    def _to_response(
        med     : MEDICINE_MODEL
        , stock : Optional[MedicineStockSummary] = None
    ) -> MedicineResponse:
        if stock is not None:
            if stock.usable <= 0:
                stock.stock_status = "OUT"
            elif med.min_stock > 0 and stock.usable <= med.min_stock:
                stock.stock_status = "LOW"
            else:
                stock.stock_status = "OK"

        return MedicineResponse(
            id                = med.id
            , code            = med.code
            , name            = med.name
            , category_code   = med.category_code
            , form_code       = med.form_code
            , form_name       = med.form.name if med.form else None
            , dosage          = med.dosage
            , unit_label      = med.unit_label
            , is_narcotic     = med.is_narcotic
            , narcotic_doc_no = med.narcotic_doc_no
            , sort_order      = med.sort_order
            , min_stock       = med.min_stock or 0
            , note            = med.note
            , status_code     = med.status_code
            , stock           = stock
        )


    @classmethod
    def list_medicines(
        cls
        , session         : Session
        , category_code   : Optional[str]  = None
        , is_narcotic     : Optional[bool] = None
        , tabs            : Optional[str]  = None
        , status_code     : Optional[str]  = "ACTIVE"
        , search          : Optional[str]  = None
        , with_stock      : bool           = False
        , department_code : Optional[str]  = None
        , limit           : int            = 100
        , offset          : int            = 0
    ) -> List[MedicineResponse]:
        query = (
            session.query(MEDICINE_MODEL)
            .options(joinedload(MEDICINE_MODEL.form))
            .filter(MEDICINE_MODEL.deleted_datetime.is_(None))
        )
        if status_code and status_code.upper() != "ALL":
            query = query.filter(MEDICINE_MODEL.status_code == status_code.upper())
        else:
            query = query.filter(MEDICINE_MODEL.status_code != STATUS_CODE_ENUM.DELETED.value)

        if tabs:
            query = _apply_tabs_filter(query, tabs)
        if category_code:
            query = query.filter(MEDICINE_MODEL.category_code == category_code)
        if is_narcotic is not None:
            query = query.filter(MEDICINE_MODEL.is_narcotic == is_narcotic)
        if search:
            pattern = f"%{search}%"
            query   = query.filter(
                or_(
                    MEDICINE_MODEL.name.ilike(pattern)
                    , MEDICINE_MODEL.code.ilike(pattern)
                    , MEDICINE_MODEL.dosage.ilike(pattern)
                )
            )

        rows = (
            query.order_by(
                MEDICINE_MODEL.category_code
                , MEDICINE_MODEL.sort_order
                , MEDICINE_MODEL.name
            )
            .offset(offset)
            .limit(limit)
            .all()
        )

        stock_map: Dict[UUID, MedicineStockSummary] = {}
        if with_stock:
            stock_map = cls._compute_stock_map(
                session           = session
                , medicine_ids    = [m.id for m in rows]
                , department_code = department_code
            )

        return [
            cls._to_response(
                med     = m
                , stock = (stock_map.get(m.id, MedicineStockSummary()) if with_stock else None)
            )
            for m in rows
        ]


    @staticmethod
    def get_medicine(session: Session, medicine_id: UUID) -> MEDICINE_MODEL:
        med = (
            session.query(MEDICINE_MODEL)
            .options(joinedload(MEDICINE_MODEL.form))
            .filter(
                MEDICINE_MODEL.id == medicine_id
                , MEDICINE_MODEL.deleted_datetime.is_(None)
            )
            .first()
        )
        if not med:
            logger.warn(
                "MedicineService.get_medicine: not found"
                , f"medicine_id: {medicine_id}"
            )
            raise HTTPException(
                status_code = status.HTTP_404_NOT_FOUND
                , detail    = "Medicine not found."
            )
        return med


    @classmethod
    def create_medicine(cls, session: Session, payload: MedicineCreate, username: str) -> MedicineResponse:
        code = (payload.code or "").strip() or _generate_medicine_code(payload.name)
        existing = session.query(MEDICINE_MODEL).filter(MEDICINE_MODEL.code == code).first()
        if existing:
            logger.warn(
                "MedicineService.create_medicine: duplicate code"
                , f"code: {code}"
                , f"username: {username}"
            )
            raise HTTPException(
                status_code = status.HTTP_409_CONFLICT
                , detail    = "Medicine code already exists."
            )

        data         = payload.model_dump()
        data["code"] = code
        med          = MEDICINE_MODEL(
            **data
            , created_by = username
        )
        session.add(med)
        session.commit()
        session.refresh(med)
        med = cls.get_medicine(session, med.id)
        logger.info(
            "MedicineService.create_medicine: created"
            , f"medicine_id: {med.id}"
            , f"code: {med.code}"
            , f"username: {username}"
        )
        return cls._to_response(med)


    @classmethod
    def update_medicine(
        cls
        , session     : Session
        , medicine_id : UUID
        , payload     : MedicineUpdate
        , username    : str
    ) -> MedicineResponse:
        med = cls.get_medicine(session, medicine_id)
        for field, value in payload.model_dump(exclude_unset = True).items():
            setattr(med, field, value)
        med.updated_by       = username
        med.updated_datetime = utc_now_naive()
        session.commit()
        session.refresh(med)
        med = cls.get_medicine(session, med.id)
        logger.info(
            "MedicineService.update_medicine: updated"
            , f"medicine_id: {medicine_id}"
            , f"username: {username}"
        )
        return cls._to_response(med)


    @classmethod
    def delete_medicine(cls, session: Session, medicine_id: UUID, username: str) -> dict:
        med = cls.get_medicine(session, medicine_id)
        has_history = (
            session.query(STOCK_BATCH_MODEL.id)
            .filter(STOCK_BATCH_MODEL.medicine_id == medicine_id)
            .first()
            is not None
            or session.query(PATIENT_DISPENSING_ITEM_MODEL.id)
            .filter(PATIENT_DISPENSING_ITEM_MODEL.medicine_id == medicine_id)
            .first()
            is not None
            or session.query(STOCK_MOVEMENT_MODEL.id)
            .filter(STOCK_MOVEMENT_MODEL.medicine_id == medicine_id)
            .first()
            is not None
        )
        now_utc = utc_now_naive()
        if has_history:
            med.status_code      = STATUS_CODE_ENUM.INACTIVE.value
            med.updated_by       = username
            med.updated_datetime = now_utc
            session.commit()
            logger.info(
                "MedicineService.delete_medicine: deactivated (has history)"
                , f"medicine_id: {medicine_id}"
                , f"username: {username}"
            )
            return {"id": str(medicine_id), "deleted": False, "deactivated": True}

        med.status_code      = STATUS_CODE_ENUM.DELETED.value
        med.deleted_by       = username
        med.deleted_datetime = now_utc
        session.commit()
        logger.info(
            "MedicineService.delete_medicine: soft-deleted"
            , f"medicine_id: {medicine_id}"
            , f"username: {username}"
        )
        return {"id": str(medicine_id), "deleted": True, "deactivated": False}


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
