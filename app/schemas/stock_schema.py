from datetime import date, datetime
from decimal  import Decimal
from typing   import List, Optional
from uuid     import UUID

from pydantic import BaseModel, ConfigDict, Field


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
    source          : Optional[str]  = None
    total_qty       : Decimal        = Field(..., gt = 0)
    input_date      : Optional[date] = None
    expire_date     : Optional[date] = None
    note            : Optional[str]  = None


class StockBatchBulkItem(BaseModel):
    medicine_id   : Optional[UUID] = None
    medicine_code : Optional[str]  = None
    batch_no      : Optional[str]  = None
    source        : Optional[str]  = None
    total_qty     : Decimal        = Field(..., gt = 0)
    input_date    : Optional[date] = None
    expire_date   : Optional[date] = None
    note          : Optional[str]  = None


class StockBatchBulkCreate(BaseModel):
    department_code : str                      = "SURGICAL_ICU"
    items           : List[StockBatchBulkItem] = Field(..., min_length = 1, max_length = 200)


class StockBatchUpdate(BaseModel):
    total_qty   : Optional[Decimal] = Field(None, gt = 0)
    input_date  : Optional[date]    = None
    expire_date : Optional[date]    = None
    batch_no    : Optional[str]     = None
    source      : Optional[str]     = None
    note        : Optional[str]     = None


class StockBatchResponse(BaseModel):
    id               : UUID
    department_code  : str
    medicine_id      : UUID
    medicine_code    : Optional[str]      = None
    medicine_name    : Optional[str]      = None
    form_code        : Optional[str]      = None
    dosage           : Optional[str]      = None
    category_code    : Optional[str]      = None
    is_narcotic      : Optional[bool]     = None
    batch_no         : Optional[str]      = None
    source           : Optional[str]      = None
    total_qty        : Decimal
    remaining_qty    : Decimal
    input_date       : date
    expire_date      : Optional[date]     = None
    note             : Optional[str]      = None
    created_by       : Optional[str]      = None
    created_by_name  : Optional[str]      = None
    created_datetime : Optional[datetime] = None

    model_config = ConfigDict(from_attributes = True)


class StockWriteOffCreate(BaseModel):
    batch_id      : UUID
    quantity      : Decimal        = Field(..., gt = 0)
    movement_type : str            = "EXPIRED"  # EXPIRED | DAMAGED | ADJUSTMENT
    movement_date : Optional[date] = None
    note          : Optional[str]  = None


class StockMovementResponse(BaseModel):
    id               : UUID
    department_code  : str
    medicine_id      : UUID
    batch_id         : Optional[UUID]     = None
    batch_no         : Optional[str]      = None
    batch_source     : Optional[str]      = None
    patient_name     : Optional[str]      = None
    movement_type    : str
    movement_date    : date
    quantity         : Decimal
    note             : Optional[str]      = None
    created_by       : Optional[str]      = None
    created_by_name  : Optional[str]      = None
    created_datetime : Optional[datetime] = None

    model_config = ConfigDict(from_attributes = True)
