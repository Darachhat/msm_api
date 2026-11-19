from datetime import date
from decimal  import Decimal
from typing   import List, Optional
from uuid     import UUID

from pydantic import BaseModel


class StockTabSummary(BaseModel):
    tab_code            : str  # TABLET | INJECTION | NARCOTIC
    medicine_count      : int
    total_remaining_qty : Decimal


class NearlyExpiredBatchItem(BaseModel):
    batch_id          : UUID
    medicine_id       : UUID
    medicine_code     : str
    medicine_name     : str
    category_code     : str
    batch_no          : Optional[str] = None
    remaining_qty     : Decimal
    input_date        : date
    expire_date       : date
    days_until_expiry : int


class DashboardSummaryResponse(BaseModel):
    total_medicines        : int
    total_patients         : int
    total_dispensing_today : int
    stock_by_tab           : List[StockTabSummary]
    nearly_expired_count   : int
    nearly_expired_batches : List[NearlyExpiredBatchItem]
    low_stock_medicines    : List[dict]
