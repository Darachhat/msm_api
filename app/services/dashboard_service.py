from datetime import date, timedelta
from decimal  import Decimal
from typing   import Optional
from sqlalchemy.orm import Session, joinedload

from app.core.enum              import MEDICINE_CATEGORY_ENUM, STATUS_CODE_ENUM
from app.core.log               import logger
from app.models.base_data_model import MEDICINE_MODEL
from app.models.data_model      import (
    PATIENT_DISPENSING_MODEL
    , PATIENT_MODEL
    , STOCK_BATCH_MODEL
)
from app.schemas.dashboard_schema import (
    DashboardSummaryResponse
    , NearlyExpiredBatchItem
    , StockTabSummary
)


class DashboardService:

    @staticmethod
    def get_summary(
        session                : Session
        , expiring_within_days : Optional[int] = 30
        , department_code      : Optional[str] = None
    ) -> DashboardSummaryResponse:
        today = date.today()

        total_medicines = (
            session.query(MEDICINE_MODEL)
            .filter(
                MEDICINE_MODEL.status_code == STATUS_CODE_ENUM.ACTIVE.value
                , MEDICINE_MODEL.deleted_datetime.is_(None)
            )
            .count()
        )
        total_patients = (
            session.query(PATIENT_MODEL)
            .filter(
                PATIENT_MODEL.status_code == STATUS_CODE_ENUM.ACTIVE.value
                , PATIENT_MODEL.deleted_datetime.is_(None)
            )
            .count()
        )
        disp_q = session.query(PATIENT_DISPENSING_MODEL).filter(
            PATIENT_DISPENSING_MODEL.dispense_date == today
            , PATIENT_DISPENSING_MODEL.status_code == STATUS_CODE_ENUM.ACTIVE.value
            , PATIENT_DISPENSING_MODEL.deleted_datetime.is_(None)
        )
        if department_code:
            disp_q = disp_q.filter(PATIENT_DISPENSING_MODEL.department_code == department_code)
        total_dispensing_today = disp_q.count()

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

        tab_totals = {
            "TABLET"    : {"meds": set(), "qty": Decimal("0")}
            , "INJECTION": {"meds": set(), "qty": Decimal("0")}
            , "NARCOTIC" : {"meds": set(), "qty": Decimal("0")}
        }
        for b in batches:
            if not b.medicine:
                continue
            if b.medicine.is_narcotic:
                tab_totals["NARCOTIC"]["meds"].add(b.medicine_id)
                tab_totals["NARCOTIC"]["qty"] += b.remaining_qty or Decimal("0")
            elif b.medicine.category_code == MEDICINE_CATEGORY_ENUM.TABLET.value:
                tab_totals["TABLET"]["meds"].add(b.medicine_id)
                tab_totals["TABLET"]["qty"] += b.remaining_qty or Decimal("0")
            else:
                tab_totals["INJECTION"]["meds"].add(b.medicine_id)
                tab_totals["INJECTION"]["qty"] += b.remaining_qty or Decimal("0")

        stock_by_tab = [
            StockTabSummary(
                tab_code              = k
                , medicine_count      = len(v["meds"])
                , total_remaining_qty = v["qty"]
            )
            for k, v in tab_totals.items()
        ]

        nearly_expired: list[NearlyExpiredBatchItem] = []
        if expiring_within_days is not None:
            cutoff = today + timedelta(days = expiring_within_days)
            for b in batches:
                if b.expire_date and b.expire_date <= cutoff and b.medicine:
                    nearly_expired.append(
                        NearlyExpiredBatchItem(
                            batch_id            = b.id
                            , medicine_id       = b.medicine_id
                            , medicine_code     = b.medicine.code
                            , medicine_name     = b.medicine.name
                            , category_code     = b.medicine.category_code
                            , batch_no          = b.batch_no
                            , remaining_qty     = b.remaining_qty
                            , input_date        = b.input_date
                            , expire_date       = b.expire_date
                            , days_until_expiry = (b.expire_date - today).days
                        )
                    )
            nearly_expired.sort(key = lambda x: x.expire_date)

        # Aggregate low stock medicines (remaining <= 10 across active batches)
        med_qty_map: dict = {}
        for b in batches:
            if not b.medicine:
                continue
            if b.medicine_id not in med_qty_map:
                med_qty_map[b.medicine_id] = {
                    "medicine_id"     : str(b.medicine_id)
                    , "medicine_code" : b.medicine.code
                    , "medicine_name" : b.medicine.name
                    , "category_code" : b.medicine.category_code
                    , "remaining_qty" : Decimal("0")
                }
            med_qty_map[b.medicine_id]["remaining_qty"] += b.remaining_qty or Decimal("0")

        low_stock = [v for v in med_qty_map.values() if v["remaining_qty"] <= Decimal("10")]

        logger.info(
            "DashboardService.get_summary: completed"
            , f"department_code: {department_code}"
            , f"total_medicines: {total_medicines}"
            , f"total_patients: {total_patients}"
            , f"dispensing_today: {total_dispensing_today}"
            , f"nearly_expired: {len(nearly_expired)}"
            , f"low_stock: {len(low_stock)}"
        )

        return DashboardSummaryResponse(
            total_medicines          = total_medicines
            , total_patients         = total_patients
            , total_dispensing_today = total_dispensing_today
            , stock_by_tab           = stock_by_tab
            , nearly_expired_count   = len(nearly_expired)
            , nearly_expired_batches = nearly_expired
            , low_stock_medicines    = low_stock
        )
