from datetime import date
from decimal  import Decimal
from typing   import List, Optional
from uuid     import UUID

from pydantic import ConfigDict, BaseModel, Field


class StockLedgerUpsertItem(BaseModel):
    medicine_id   : Optional[UUID]    = None
    medicine_code : Optional[str]     = None
    opening_qty   : Decimal           = Field(default = Decimal("0"))
    added_qty     : Decimal           = Field(default = Decimal("0"))
    used_qty      : Decimal           = Field(default = Decimal("0"))
    remaining_qty : Optional[Decimal] = None
    requested_qty : Decimal           = Field(default = Decimal("0"))
    supplied_qty  : Decimal           = Field(default = Decimal("0"))
    note          : Optional[str]     = None


class StockLedgerBatchUpsert(BaseModel):
    stock_date      : date
    department_code : str                         = "SURGICAL_ICU"
    items           : List[StockLedgerUpsertItem] = Field(..., min_length = 1)


class StockLedgerResponse(BaseModel):
    id              : UUID
    stock_date      : date
    department_code : str
    medicine_id     : UUID
    medicine_code   : Optional[str] = None
    medicine_name   : Optional[str] = None
    form_code       : Optional[str] = None
    dosage          : Optional[str] = None
    opening_qty     : Decimal
    added_qty       : Decimal
    used_qty        : Decimal
    remaining_qty   : Decimal
    requested_qty   : Decimal
    supplied_qty    : Decimal
    note            : Optional[str] = None

    model_config = ConfigDict(from_attributes = True)


class StockBatchCreate(BaseModel):
    department_code : str            = "SURGICAL_ICU"
    medicine_id     : Optional[UUID] = None
    medicine_code   : Optional[str]  = None
    batch_no        : Optional[str]  = None
    total_qty       : Decimal        = Field(..., gt = 0)
    input_date      : Optional[date] = None  # Defaults to today
    expire_date     : Optional[date] = None  # Optional per user requirement
    note            : Optional[str]  = None


class StockBatchResponse(BaseModel):
    id              : UUID
    department_code : str
    medicine_id     : UUID
    medicine_code   : Optional[str]  = None
    medicine_name   : Optional[str]  = None
    category_code   : Optional[str]  = None
    is_narcotic     : Optional[bool] = None
    batch_no        : Optional[str]  = None
    total_qty       : Decimal
    remaining_qty   : Decimal
    input_date      : date
    expire_date     : Optional[date] = None
    note            : Optional[str]  = None

    model_config = ConfigDict(from_attributes = True)
