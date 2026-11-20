from datetime import date
from decimal  import Decimal
from typing   import List, Optional
from uuid     import UUID

from pydantic import BaseModel


class StockStatusByTabItem(BaseModel):
    tab_code : str  # INJECTION | TABLET | NARCOTIC
    ok       : int  = 0
    low      : int  = 0
    out      : int  = 0
    total    : int  = 0


class LowStockMedicineItem(BaseModel):
    medicine_id    : UUID
    medicine_code  : str
    medicine_name  : str
    form_code      : str
    dosage         : Optional[str]  = None
    category_code  : str
    is_narcotic    : bool           = False
    min_stock      : int            = 0
    balance        : Decimal        = Decimal("0")
    usable         : Decimal        = Decimal("0")
    stock_status   : str            = "OUT"
    nearest_expiry : Optional[date] = None


class NearlyExpiredBatchItem(BaseModel):
    batch_id          : UUID
    medicine_id       : UUID
    medicine_code     : str
    medicine_name     : str
    form_code         : Optional[str] = None
    dosage            : Optional[str] = None
    category_code     : str
    is_narcotic       : bool          = False
    batch_no          : Optional[str] = None
    remaining_qty     : Decimal
    input_date        : date
    expire_date       : date
    days_until_expiry : int


class UsageTrendPoint(BaseModel):
    day        : date
    injection  : Decimal = Decimal("0")
    tablet     : Decimal = Decimal("0")
    narcotic   : Decimal = Decimal("0")
    admissions : int     = 0


class TopUsedMedicineItem(BaseModel):
    medicine_id   : UUID
    medicine_name : str
    dosage        : Optional[str] = None
    category_code : str
    is_narcotic   : bool          = False
    quantity      : Decimal       = Decimal("0")


class DashboardSummaryResponse(BaseModel):
    today                  : date
    expiry_warn_days       : int
    total_medicines        : int
    admitted_count         : int
    admitted_today         : int
    usage_qty_today        : Decimal
    usage_lines_today      : int
    patients_treated_today : int
    low_stock_count        : int
    out_of_stock_count     : int
    expiring_batch_count   : int
    expired_batch_count    : int
    stock_status_by_tab    : List[StockStatusByTabItem]
    low_stock_list         : List[LowStockMedicineItem]
    nearly_expired_batches : List[NearlyExpiredBatchItem]
    usage_trend            : List[UsageTrendPoint]
    top_used_this_month    : List[TopUsedMedicineItem]
