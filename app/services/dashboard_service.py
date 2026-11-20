from datetime import date, timedelta
from decimal  import Decimal
from typing   import Dict, List, Optional
from uuid     import UUID

from sqlalchemy.orm import Session, joinedload

from app.core.enum              import MEDICINE_CATEGORY_ENUM, STATUS_CODE_ENUM
from app.core.log               import logger
from app.models.base_data_model import MEDICINE_MODEL
from app.models.data_model      import (
    PATIENT_DISPENSING_ITEM_MODEL
    , PATIENT_DISPENSING_MODEL
    , PATIENT_MODEL
    , STOCK_BATCH_MODEL
)
from app.schemas.dashboard_schema import (
    DashboardSummaryResponse
    , LowStockMedicineItem
    , NearlyExpiredBatchItem
    , StockStatusByTabItem
    , TopUsedMedicineItem
    , UsageTrendPoint
)


def _med_tab(med: MEDICINE_MODEL) -> str:
    if med.is_narcotic:
        return "NARCOTIC"
    if med.category_code == MEDICINE_CATEGORY_ENUM.TABLET.value:
        return "TABLET"
    return "INJECTION"


class DashboardService:

    @staticmethod
    def get_summary(
        session                : Session
        , expiring_within_days : Optional[int] = 90
        , department_code      : Optional[str] = None
    ) -> DashboardSummaryResponse:
        today     = date.today()
        warn_days = expiring_within_days if expiring_within_days is not None else 90
        cutoff    = today + timedelta(days = warn_days)

        # 1. Active medicines
        medicines = (
            session.query(MEDICINE_MODEL)
            .filter(
                MEDICINE_MODEL.status_code == STATUS_CODE_ENUM.ACTIVE.value
                , MEDICINE_MODEL.deleted_datetime.is_(None)
            )
            .order_by(MEDICINE_MODEL.sort_order, MEDICINE_MODEL.name)
            .all()
        )
        total_medicines = len(medicines)

        # 2. Patient admission KPIs
        patient_q = session.query(PATIENT_MODEL).filter(
            PATIENT_MODEL.status_code == STATUS_CODE_ENUM.ACTIVE.value
            , PATIENT_MODEL.deleted_datetime.is_(None)
        )
        admitted_count = patient_q.filter(PATIENT_MODEL.date_out.is_(None)).count()
        admitted_today = patient_q.filter(PATIENT_MODEL.date_in == today).count()

        # 3. Stock batches
        batch_q = (
            session.query(STOCK_BATCH_MODEL)
            .options(joinedload(STOCK_BATCH_MODEL.medicine))
            .filter(
                STOCK_BATCH_MODEL.status_code == STATUS_CODE_ENUM.ACTIVE.value
                , STOCK_BATCH_MODEL.deleted_datetime.is_(None)
                , STOCK_BATCH_MODEL.remaining_qty > 0
            )
        )
        if department_code:
            batch_q = batch_q.filter(STOCK_BATCH_MODEL.department_code == department_code)
        batches = batch_q.all()

        med_balance : Dict[UUID, Decimal]        = {}
        med_usable  : Dict[UUID, Decimal]        = {}
        med_nearest : Dict[UUID, Optional[date]] = {}
        nearly_expired : List[NearlyExpiredBatchItem] = []
        expired_batch_count = 0

        for b in batches:
            rem = b.remaining_qty or Decimal("0")
            med_balance[b.medicine_id] = med_balance.get(b.medicine_id, Decimal("0")) + rem

            if b.expire_date is not None and b.expire_date < today:
                expired_batch_count += 1
            else:
                med_usable[b.medicine_id] = med_usable.get(b.medicine_id, Decimal("0")) + rem
                if b.expire_date is not None:
                    cur = med_nearest.get(b.medicine_id)
                    if cur is None or b.expire_date < cur:
                        med_nearest[b.medicine_id] = b.expire_date
                    if b.expire_date <= cutoff and b.medicine:
                        nearly_expired.append(
                            NearlyExpiredBatchItem(
                                batch_id            = b.id
                                , medicine_id       = b.medicine_id
                                , medicine_code     = b.medicine.code
                                , medicine_name     = b.medicine.name
                                , form_code         = b.medicine.form_code
                                , dosage            = b.medicine.dosage
                                , category_code     = b.medicine.category_code
                                , is_narcotic       = bool(b.medicine.is_narcotic)
                                , batch_no          = b.batch_no
                                , remaining_qty     = rem
                                , input_date        = b.input_date
                                , expire_date       = b.expire_date
                                , days_until_expiry = (b.expire_date - today).days
                            )
                        )
        nearly_expired.sort(key = lambda x: x.expire_date)

        # 4. Stock status by tab + low/out-of-stock list
        tab_stats = {
            "INJECTION" : {"ok": 0, "low": 0, "out": 0, "total": 0}
            , "TABLET"  : {"ok": 0, "low": 0, "out": 0, "total": 0}
            , "NARCOTIC": {"ok": 0, "low": 0, "out": 0, "total": 0}
        }
        low_stock_list     : List[LowStockMedicineItem] = []
        low_stock_count    = 0
        out_of_stock_count = 0

        for med in medicines:
            tab     = _med_tab(med)
            bal     = med_balance.get(med.id, Decimal("0"))
            usable  = med_usable.get(med.id, Decimal("0"))
            min_stk = med.min_stock or 0

            tab_stats[tab]["total"] += 1
            if usable <= 0:
                st = "OUT"
                tab_stats[tab]["out"] += 1
                out_of_stock_count    += 1
            elif min_stk > 0 and usable <= min_stk:
                st = "LOW"
                tab_stats[tab]["low"] += 1
                low_stock_count       += 1
            else:
                st = "OK"
                tab_stats[tab]["ok"] += 1

            if st in ("OUT", "LOW"):
                low_stock_list.append(
                    LowStockMedicineItem(
                        medicine_id      = med.id
                        , medicine_code  = med.code
                        , medicine_name  = med.name
                        , form_code      = med.form_code
                        , dosage         = med.dosage
                        , category_code  = med.category_code
                        , is_narcotic    = bool(med.is_narcotic)
                        , min_stock      = min_stk
                        , balance        = bal
                        , usable         = usable
                        , stock_status   = st
                        , nearest_expiry = med_nearest.get(med.id)
                    )
                )

        low_stock_list.sort(key = lambda x: (0 if x.stock_status == "OUT" else 1, x.usable, x.medicine_name))

        stock_status_by_tab = [
            StockStatusByTabItem(
                tab_code = k
                , ok     = v["ok"]
                , low    = v["low"]
                , out    = v["out"]
                , total  = v["total"]
            )
            for k, v in tab_stats.items()
        ]

        # 5. Usage today + 14-day trend + top used this month
        trend_start = today - timedelta(days = 13)
        month_start = today.replace(day = 1)
        query_start = min(trend_start, month_start)

        disp_q = (
            session.query(PATIENT_DISPENSING_ITEM_MODEL)
            .join(
                PATIENT_DISPENSING_MODEL
                , PATIENT_DISPENSING_ITEM_MODEL.dispensing_id == PATIENT_DISPENSING_MODEL.id
            )
            .options(
                joinedload(PATIENT_DISPENSING_ITEM_MODEL.dispensing)
                , joinedload(PATIENT_DISPENSING_ITEM_MODEL.medicine)
            )
            .filter(
                PATIENT_DISPENSING_MODEL.dispense_date >= query_start
                , PATIENT_DISPENSING_MODEL.dispense_date <= today
                , PATIENT_DISPENSING_MODEL.status_code == STATUS_CODE_ENUM.ACTIVE.value
                , PATIENT_DISPENSING_MODEL.deleted_datetime.is_(None)
                , PATIENT_DISPENSING_ITEM_MODEL.status_code == STATUS_CODE_ENUM.ACTIVE.value
                , PATIENT_DISPENSING_ITEM_MODEL.deleted_datetime.is_(None)
            )
        )
        if department_code:
            disp_q = disp_q.filter(PATIENT_DISPENSING_MODEL.department_code == department_code)
        disp_items = disp_q.all()

        usage_qty_today    = Decimal("0")
        usage_lines_today  = 0
        patients_today_set = set()

        trend_map: Dict[date, dict] = {
            trend_start + timedelta(days = i): {
                "INJECTION"   : Decimal("0")
                , "TABLET"    : Decimal("0")
                , "NARCOTIC"  : Decimal("0")
                , "admissions": 0
            }
            for i in range(14)
        }
        top_map: Dict[UUID, TopUsedMedicineItem] = {}

        for it in disp_items:
            d = it.dispensing
            m = it.medicine
            if not d or not m:
                continue
            qty = it.quantity or Decimal("0")
            tab = _med_tab(m)

            if d.dispense_date == today:
                usage_qty_today   += qty
                usage_lines_today += 1
                patients_today_set.add(str(d.patient_id) if d.patient_id else d.patient_name.strip().lower())

            if d.dispense_date in trend_map:
                trend_map[d.dispense_date][tab] += qty

            if d.dispense_date >= month_start:
                if m.id not in top_map:
                    top_map[m.id] = TopUsedMedicineItem(
                        medicine_id     = m.id
                        , medicine_name = m.name
                        , dosage        = m.dosage
                        , category_code = m.category_code
                        , is_narcotic   = bool(m.is_narcotic)
                        , quantity      = Decimal("0")
                    )
                top_map[m.id].quantity += qty

        # Admissions per day in 14-day window
        recent_patients = (
            patient_q.filter(
                PATIENT_MODEL.date_in >= trend_start
                , PATIENT_MODEL.date_in <= today
            )
            .all()
        )
        for p in recent_patients:
            if p.date_in in trend_map:
                trend_map[p.date_in]["admissions"] += 1

        usage_trend = [
            UsageTrendPoint(
                day          = day_key
                , injection  = vals["INJECTION"]
                , tablet     = vals["TABLET"]
                , narcotic   = vals["NARCOTIC"]
                , admissions = vals["admissions"]
            )
            for day_key, vals in sorted(trend_map.items())
        ]
        top_used_this_month = sorted(
            top_map.values()
            , key     = lambda x: x.quantity
            , reverse = True
        )[:10]

        logger.info(
            "DashboardService.get_summary: completed"
            , f"department_code: {department_code}"
            , f"total_medicines: {total_medicines}"
            , f"admitted_count: {admitted_count}"
            , f"low_stock: {low_stock_count}"
            , f"out_of_stock: {out_of_stock_count}"
        )

        return DashboardSummaryResponse(
            today                    = today
            , expiry_warn_days       = warn_days
            , total_medicines        = total_medicines
            , admitted_count         = admitted_count
            , admitted_today         = admitted_today
            , usage_qty_today        = usage_qty_today
            , usage_lines_today      = usage_lines_today
            , patients_treated_today = len(patients_today_set)
            , low_stock_count        = low_stock_count
            , out_of_stock_count     = out_of_stock_count
            , expiring_batch_count   = len(nearly_expired)
            , expired_batch_count    = expired_batch_count
            , stock_status_by_tab    = stock_status_by_tab
            , low_stock_list         = low_stock_list
            , nearly_expired_batches = nearly_expired
            , usage_trend            = usage_trend
            , top_used_this_month    = top_used_this_month
        )
