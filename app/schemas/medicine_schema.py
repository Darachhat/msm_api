from datetime import date
from decimal  import Decimal
from typing   import Optional
from uuid     import UUID

from pydantic import BaseModel, ConfigDict, Field


class MedicineStockSummary(BaseModel):
    balance        : Decimal        = Decimal("0")
    usable         : Decimal        = Decimal("0")
    stock_status   : str            = "OUT"  # OK | LOW | OUT
    expired_qty    : Decimal        = Decimal("0")
    expiring_qty   : Decimal        = Decimal("0")
    nearest_expiry : Optional[date] = None
    batch_count    : int            = 0


class MedicineCreate(BaseModel):
    code            : Optional[str] = Field(None, max_length = 100)
    name            : str           = Field(..., max_length = 255)
    category_code   : str           = Field(..., max_length = 50)
    form_code       : str           = Field(..., max_length = 50)
    dosage          : Optional[str] = None
    unit_label      : Optional[str] = None
    is_narcotic     : bool          = False
    narcotic_doc_no : Optional[str] = None
    sort_order      : int           = 0
    min_stock       : int           = Field(default = 0, ge = 0)
    note            : Optional[str] = None


class MedicineUpdate(BaseModel):
    name            : Optional[str]  = None
    category_code   : Optional[str]  = None
    form_code       : Optional[str]  = None
    dosage          : Optional[str]  = None
    unit_label      : Optional[str]  = None
    is_narcotic     : Optional[bool] = None
    narcotic_doc_no : Optional[str]  = None
    sort_order      : Optional[int]  = None
    min_stock       : Optional[int]  = Field(None, ge = 0)
    note            : Optional[str]  = None
    status_code     : Optional[str]  = None


class MedicineResponse(BaseModel):
    id              : UUID
    code            : str
    name            : str
    category_code   : str
    form_code       : str
    form_name       : Optional[str]                  = None
    dosage          : Optional[str]                  = None
    unit_label      : Optional[str]                  = None
    is_narcotic     : bool
    narcotic_doc_no : Optional[str]                  = None
    sort_order      : int
    min_stock       : int                            = 0
    note            : Optional[str]                  = None
    status_code     : str
    stock           : Optional[MedicineStockSummary] = None

    model_config = ConfigDict(from_attributes = True)


class MedicineFormResponse(BaseModel):
    id           : UUID
    code         : str
    name         : str
    name_kh      : Optional[str] = None
    unit_label   : Optional[str] = None
    record_order : int           = 0

    model_config = ConfigDict(from_attributes = True)


class DepartmentResponse(BaseModel):
    id               : UUID
    code             : str
    name             : str
    name_kh          : str
    hospital_name    : Optional[str] = None
    hospital_name_kh : Optional[str] = None
    doc_number       : Optional[str] = None

    model_config = ConfigDict(from_attributes = True)
