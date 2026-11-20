from datetime import date, timedelta
from decimal  import Decimal
from typing   import Dict, List, Optional
from uuid     import UUID

from sqlalchemy     import and_, or_
from sqlalchemy.orm import Session, joinedload

from app.core.constants         import utc_now_naive
from app.core.enum              import STATUS_CODE_ENUM
from app.models.base_data_model import MEDICINE_MODEL
from app.models.data_model      import (
    PATIENT_DISPENSING_ITEM_MODEL
    , PATIENT_DISPENSING_MODEL
    , PATIENT_MODEL
    , STOCK_LEDGER_MODEL
    , STOCK_MOVEMENT_MODEL
)
from app.schemas.dispensing_schema import DispensingLineResponse
from app.schemas.report_schema     import (
    DailySheetReportResponse
    , DailySheetRow
    , MedicineUsagePatientEntry
    , MedicineUsageReportItem
    , MedicineUsageReportResponse
    , ReportMedicineRef
    , ReportRequestsUpsert
    , StockSummaryReportResponse
    , StockSummaryRow
)
from app.services.dispensing_service import DispensingService

_WRITEOFF_TYPES = frozenset({"EXPIRED", "DAMAGED", "ADJUSTMENT"})


def _apply_med_tabs(query, tabs: Optional[str]):
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


def _med_ref(med: MEDICINE_MODEL) -> ReportMedicineRef:
    return ReportMedicineRef(
        id              = med.id
        , code          = med.code
        , name          = med.name
        , form_code     = med.form_code
        , form_name     = med.form.name if med.form else None
        , dosage        = med.dosage
        , category_code = med.category_code
        , is_narcotic   = bool(med.is_narcotic)
        , sort_order    = med.sort_order or 0
        , status_code   = med.status_code
    )


class ReportDataService:
    """Computes structured JSON reports consumed by msm_front report views."""

    @staticmethod
    def stock_summary(
        session           : Session
        , start_date      : date
        , end_date        : date
        , tabs            : Optional[str] = None
        , department_code : Optional[str] = None
    ) -> StockSummaryReportResponse:
        med_q = (
            session.query(MEDICINE_MODEL)
            .options(joinedload(MEDICINE_MODEL.form))
            .filter(MEDICINE_MODEL.deleted_datetime.is_(None))
        )
        med_q = _apply_med_tabs(med_q, tabs)
        meds  = med_q.order_by(MEDICINE_MODEL.sort_order, MEDICINE_MODEL.name).all()
        med_ids = [m.id for m in meds]

        num_days = max(0, (end_date - start_date).days) + 1
        days     = [(start_date + timedelta(days = i)).isoformat() for i in range(num_days)]

        if not med_ids:
            return StockSummaryReportResponse(
                start_date = start_date
                , end_date = end_date
                , days     = days
                , rows     = []
            )

        # Fetch all movements up to end_date for these medicines
        mv_q = session.query(STOCK_MOVEMENT_MODEL).filter(
            STOCK_MOVEMENT_MODEL.medicine_id.in_(med_ids)
            , STOCK_MOVEMENT_MODEL.movement_date <= end_date
            , STOCK_MOVEMENT_MODEL.status_code == STATUS_CODE_ENUM.ACTIVE.value
            , STOCK_MOVEMENT_MODEL.deleted_datetime.is_(None)
        )
        if department_code:
            mv_q = mv_q.filter(STOCK_MOVEMENT_MODEL.department_code == department_code)

        opening_map   : Dict[UUID, Decimal]            = {}
        received_map  : Dict[UUID, Decimal]            = {}
        writeoff_map  : Dict[UUID, Decimal]            = {}
        daily_map     : Dict[UUID, Dict[str, Decimal]] = {}

        for mv in mv_q.all():
            qty = mv.quantity or Decimal("0")
            mid = mv.medicine_id
            if mv.movement_date < start_date:
                delta = qty if mv.movement_type == "IN" else -qty
                opening_map[mid] = opening_map.get(mid, Decimal("0")) + delta
            else:
                if mv.movement_type == "IN":
                    received_map[mid] = received_map.get(mid, Decimal("0")) + qty
                elif mv.movement_type == "USAGE":
                    d_str = mv.movement_date.isoformat()
                    m_day = daily_map.setdefault(mid, {})
                    m_day[d_str] = m_day.get(d_str, Decimal("0")) + qty
                elif mv.movement_type in _WRITEOFF_TYPES:
                    writeoff_map[mid] = writeoff_map.get(mid, Decimal("0")) + qty

        # Fetch saved requisition (requested_qty / supplied_qty) stored at end_date
        req_q = session.query(STOCK_LEDGER_MODEL).filter(
            STOCK_LEDGER_MODEL.medicine_id.in_(med_ids)
            , STOCK_LEDGER_MODEL.stock_date == end_date
            , STOCK_LEDGER_MODEL.status_code == STATUS_CODE_ENUM.ACTIVE.value
            , STOCK_LEDGER_MODEL.deleted_datetime.is_(None)
        )
        if department_code:
            req_q = req_q.filter(STOCK_LEDGER_MODEL.department_code == department_code)
        req_map: Dict[UUID, STOCK_LEDGER_MODEL] = {r.medicine_id: r for r in req_q.all()}

        rows: List[StockSummaryRow] = []
        for med in meds:
            opening   = opening_map.get(med.id, Decimal("0"))
            received  = received_map.get(med.id, Decimal("0"))
            d_used    = daily_map.get(med.id, {})
            used      = sum(d_used.values(), Decimal("0"))
            write_off = writeoff_map.get(med.id, Decimal("0"))
            closing   = opening + received - used - write_off
            ledger    = req_map.get(med.id)

            # Skip inactive medicines that have no stock and no activity in the period
            if (
                med.status_code != STATUS_CODE_ENUM.ACTIVE.value
                and opening == 0
                and received == 0
                and used == 0
                and write_off == 0
            ):
                continue

            rows.append(
                StockSummaryRow(
                    medicine        = _med_ref(med)
                    , opening       = opening
                    , received      = received
                    , daily_used    = d_used
                    , used          = used
                    , write_off     = write_off
                    , closing       = closing
                    , requested_qty = ledger.requested_qty if ledger else None
                    , supplied_qty  = ledger.supplied_qty if ledger else None
                )
            )

        return StockSummaryReportResponse(
            start_date = start_date
            , end_date = end_date
            , days     = days
            , rows     = rows
        )


    @staticmethod
    def save_requests(
        session    : Session
        , payload  : ReportRequestsUpsert
        , username : str
    ) -> int:
        now_utc = utc_now_naive()
        saved   = 0
        for item in payload.items:
            ledger = (
                session.query(STOCK_LEDGER_MODEL)
                .filter(
                    STOCK_LEDGER_MODEL.stock_date == payload.end_date
                    , STOCK_LEDGER_MODEL.department_code == payload.department_code
                    , STOCK_LEDGER_MODEL.medicine_id == item.medicine_id
                )
                .first()
            )
            if not ledger:
                ledger = STOCK_LEDGER_MODEL(
                    stock_date        = payload.end_date
                    , department_code = payload.department_code
                    , medicine_id     = item.medicine_id
                    , opening_qty     = Decimal("0")
                    , added_qty       = Decimal("0")
                    , used_qty        = Decimal("0")
                    , remaining_qty   = Decimal("0")
                    , requested_qty   = item.requested_qty
                    , supplied_qty    = item.supplied_qty
                    , created_by      = username
                )
                session.add(ledger)
            else:
                ledger.requested_qty    = item.requested_qty
                ledger.supplied_qty     = item.supplied_qty
                ledger.updated_by       = username
                ledger.updated_datetime = now_utc
            saved += 1
        session.commit()
        return saved


    @staticmethod
    def daily_sheet(
        session           : Session
        , start_date      : date
        , end_date        : date
        , tabs            : Optional[str] = None
        , all_columns     : bool          = False
        , department_code : Optional[str] = None
    ) -> DailySheetReportResponse:
        med_q = (
            session.query(MEDICINE_MODEL)
            .options(joinedload(MEDICINE_MODEL.form))
            .filter(
                MEDICINE_MODEL.status_code == STATUS_CODE_ENUM.ACTIVE.value
                , MEDICINE_MODEL.deleted_datetime.is_(None)
            )
        )
        med_q    = _apply_med_tabs(med_q, tabs)
        all_meds = med_q.order_by(MEDICINE_MODEL.sort_order, MEDICINE_MODEL.name).all()
        med_by_id: Dict[UUID, MEDICINE_MODEL] = {m.id: m for m in all_meds}

        item_q = (
            session.query(PATIENT_DISPENSING_ITEM_MODEL)
            .join(
                PATIENT_DISPENSING_MODEL
                , PATIENT_DISPENSING_ITEM_MODEL.dispensing_id == PATIENT_DISPENSING_MODEL.id
            )
            .options(
                joinedload(PATIENT_DISPENSING_ITEM_MODEL.dispensing)
                , joinedload(PATIENT_DISPENSING_ITEM_MODEL.medicine).joinedload(MEDICINE_MODEL.form)
            )
            .filter(
                PATIENT_DISPENSING_MODEL.dispense_date >= start_date
                , PATIENT_DISPENSING_MODEL.dispense_date <= end_date
                , PATIENT_DISPENSING_MODEL.status_code == STATUS_CODE_ENUM.ACTIVE.value
                , PATIENT_DISPENSING_MODEL.deleted_datetime.is_(None)
                , PATIENT_DISPENSING_ITEM_MODEL.status_code == STATUS_CODE_ENUM.ACTIVE.value
                , PATIENT_DISPENSING_ITEM_MODEL.deleted_datetime.is_(None)
            )
        )
        if department_code:
            item_q = item_q.filter(PATIENT_DISPENSING_MODEL.department_code == department_code)
        if tabs:
            item_q = item_q.join(MEDICINE_MODEL, PATIENT_DISPENSING_ITEM_MODEL.medicine_id == MEDICINE_MODEL.id)
            item_q = _apply_med_tabs(item_q, tabs)

        items = item_q.order_by(
            PATIENT_DISPENSING_MODEL.dispense_date.asc()
            , PATIENT_DISPENSING_ITEM_MODEL.created_datetime.asc()
        ).all()

        patient_ids = {it.dispensing.patient_id for it in items if it.dispensing and it.dispensing.patient_id}
        patients_by_id: Dict[UUID, PATIENT_MODEL] = {}
        if patient_ids:
            p_rows = session.query(PATIENT_MODEL).filter(PATIENT_MODEL.id.in_(patient_ids)).all()
            patients_by_id = {p.id: p for p in p_rows}

        used_med_map : Dict[UUID, MEDICINE_MODEL] = {}
        row_map      : Dict[str, DailySheetRow]   = {}
        totals       : Dict[str, Decimal]         = {}

        for it in items:
            d = it.dispensing
            m = it.medicine
            if not d or not m:
                continue
            used_med_map[m.id] = m
            p_key = str(d.patient_id) if d.patient_id else d.patient_name.strip().lower()
            if p_key not in row_map:
                p_rec = patients_by_id.get(d.patient_id) if d.patient_id else None
                row_map[p_key] = DailySheetRow(
                    patient_id     = d.patient_id
                    , patient_code = p_rec.patient_code if p_rec else None
                    , patient_name = p_rec.full_name if p_rec else d.patient_name
                    , sex          = p_rec.sex if p_rec else d.sex
                    , age          = p_rec.age if p_rec else d.age
                    , diagnostic   = p_rec.diagnostic if p_rec else d.diagnostic
                    , province     = p_rec.pob_province if p_rec else d.address_province
                    , date_in      = p_rec.date_in if p_rec else None
                    , quantities   = {}
                    , first_at     = it.created_datetime
                )
            row    = row_map[p_key]
            m_str  = str(m.id)
            qty    = it.quantity or Decimal("0")
            row.quantities[m_str] = row.quantities.get(m_str, Decimal("0")) + qty
            totals[m_str]         = totals.get(m_str, Decimal("0")) + qty
            if row.first_at is None or (it.created_datetime and it.created_datetime < row.first_at):
                row.first_at = it.created_datetime

        if all_columns:
            col_meds = list(all_meds)
            for mid, m in used_med_map.items():
                if mid not in med_by_id:
                    col_meds.append(m)
        else:
            col_meds = sorted(used_med_map.values(), key = lambda x: (x.sort_order or 0, x.name))

        return DailySheetReportResponse(
            start_date = start_date
            , end_date = end_date
            , columns  = [_med_ref(m) for m in col_meds]
            , rows     = list(row_map.values())
            , totals   = totals
        )


    @staticmethod
    def narcotic_lines(
        session           : Session
        , start_date      : date
        , end_date        : date
        , medicine_id     : Optional[UUID] = None
        , department_code : Optional[str]  = None
    ) -> List[DispensingLineResponse]:
        rows, _ = DispensingService.list_items(
            session           = session
            , start_date      = start_date
            , end_date        = end_date
            , medicine_id     = medicine_id
            , tabs            = "NARCOTIC"
            , department_code = department_code
            , limit           = 1000
            , offset          = 0
        )
        return rows


    @staticmethod
    def medicine_usage(
        session           : Session
        , start_date      : date
        , end_date        : date
        , tabs            : Optional[str]  = None
        , medicine_id     : Optional[UUID] = None
        , department_code : Optional[str]  = None
    ) -> MedicineUsageReportResponse:
        item_q = (
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
                , joinedload(PATIENT_DISPENSING_ITEM_MODEL.medicine).joinedload(MEDICINE_MODEL.form)
            )
            .filter(
                PATIENT_DISPENSING_MODEL.dispense_date >= start_date
                , PATIENT_DISPENSING_MODEL.dispense_date <= end_date
                , PATIENT_DISPENSING_MODEL.status_code == STATUS_CODE_ENUM.ACTIVE.value
                , PATIENT_DISPENSING_MODEL.deleted_datetime.is_(None)
                , PATIENT_DISPENSING_ITEM_MODEL.status_code == STATUS_CODE_ENUM.ACTIVE.value
                , PATIENT_DISPENSING_ITEM_MODEL.deleted_datetime.is_(None)
            )
        )
        if department_code:
            item_q = item_q.filter(PATIENT_DISPENSING_MODEL.department_code == department_code)
        if medicine_id:
            item_q = item_q.filter(PATIENT_DISPENSING_ITEM_MODEL.medicine_id == medicine_id)
        if tabs:
            item_q = _apply_med_tabs(item_q, tabs)

        grouped: Dict[UUID, dict] = {}
        for it in item_q.all():
            d = it.dispensing
            m = it.medicine
            if not d or not m:
                continue
            qty   = it.quantity or Decimal("0")
            entry = grouped.setdefault(
                m.id
                , {
                    "medicine"  : m
                    , "total"   : Decimal("0")
                    , "patients": {}
                }
            )
            entry["total"] += qty
            p_key = str(d.patient_id) if d.patient_id else d.patient_name.strip().lower()
            p_map = entry["patients"]
            if p_key not in p_map:
                p_map[p_key] = MedicineUsagePatientEntry(
                    patient_id     = d.patient_id
                    , patient_name = d.patient_name
                    , sex          = d.sex
                    , age          = d.age
                    , quantity     = Decimal("0")
                    , times        = 0
                )
            p_map[p_key].quantity += qty
            p_map[p_key].times    += 1

        report_items: List[MedicineUsageReportItem] = []
        for entry in sorted(
            grouped.values()
            , key = lambda x: (x["medicine"].sort_order or 0, x["medicine"].name)
        ):
            p_list = sorted(entry["patients"].values(), key = lambda p: p.quantity, reverse = True)
            report_items.append(
                MedicineUsageReportItem(
                    medicine        = _med_ref(entry["medicine"])
                    , total         = entry["total"]
                    , patient_count = len(p_list)
                    , patients      = p_list
                )
            )

        return MedicineUsageReportResponse(
            start_date = start_date
            , end_date = end_date
            , items    = report_items
        )
