from datetime import date, datetime
from decimal  import Decimal
from typing   import List, Optional
from uuid     import UUID

from pydantic import BaseModel, ConfigDict, Field


class DispensingItemInput(BaseModel):
    medicine_id    : Optional[UUID] = None
    medicine_code  : Optional[str]  = None
    quantity       : Decimal        = Field(..., gt = 0)
    signature_id   : Optional[UUID] = None
    signature_note : Optional[str]  = None
    note           : Optional[str]  = None


class DispensingCreate(BaseModel):
    patient_id        : Optional[UUID]            = None
    dispense_date     : date
    department_code   : str                       = "SURGICAL_ICU"
    category_code     : str                       = "TABLET"
    patient_no        : Optional[int]             = None
    patient_name      : Optional[str]             = Field(None, min_length = 1, max_length = 255)
    age               : Optional[str]             = None
    sex               : Optional[str]             = None
    diagnostic        : Optional[str]             = None
    address_province  : Optional[str]             = None
    shift_code        : Optional[str]             = None
    payment_code      : Optional[str]             = None
    doctor_name       : Optional[str]             = None
    duty_chief_name   : Optional[str]             = None
    prepared_by_name  : Optional[str]             = None
    note              : Optional[str]             = None
    items             : List[DispensingItemInput] = Field(..., min_length = 1)
    sync_stock_ledger : bool                      = True


class DispensingVisitCreate(BaseModel):
    """Frontend atomic dispensing visit payload with FEFO batch deduction."""

    patient_id      : UUID
    dispense_date   : Optional[date]            = None
    department_code : str                       = "SURGICAL_ICU"
    payment_code    : str                       = Field(..., min_length = 1, max_length = 20)
    shift_code      : Optional[str]             = Field(None, max_length = 20)
    doctor_name     : Optional[str]             = Field(None, max_length = 255)
    note            : Optional[str]             = None
    items           : List[DispensingItemInput] = Field(..., min_length = 1, max_length = 100)


class DispensingUpdate(BaseModel):
    dispense_date    : Optional[date]                      = None
    patient_no       : Optional[int]                       = None
    patient_name     : Optional[str]                       = None
    age              : Optional[str]                       = None
    sex              : Optional[str]                       = None
    diagnostic       : Optional[str]                       = None
    address_province : Optional[str]                       = None
    shift_code       : Optional[str]                       = None
    payment_code     : Optional[str]                       = None
    doctor_name      : Optional[str]                       = None
    duty_chief_name  : Optional[str]                       = None
    prepared_by_name : Optional[str]                       = None
    note             : Optional[str]                       = None
    items            : Optional[List[DispensingItemInput]] = None


class DispensingItemResponse(BaseModel):
    id             : UUID
    medicine_id    : UUID
    medicine_code  : Optional[str]  = None
    medicine_name  : Optional[str]  = None
    quantity       : Decimal
    signature_id   : Optional[UUID] = None
    signature_note : Optional[str]  = None
    note           : Optional[str]  = None

    model_config = ConfigDict(from_attributes = True)


class DispensingLineResponse(BaseModel):
    """Flattened dispensing line item used by Usage and Narcotic screens."""

    id               : UUID
    dispensing_id    : UUID
    medicine_id      : UUID
    medicine_code    : Optional[str]  = None
    medicine_name    : Optional[str]  = None
    form_code        : Optional[str]  = None
    dosage           : Optional[str]  = None
    category_code    : Optional[str]  = None
    is_narcotic      : bool           = False
    patient_id       : Optional[UUID] = None
    patient_name     : str
    sex              : Optional[str]  = None
    age              : Optional[str]  = None
    diagnostic       : Optional[str]  = None
    address_province : Optional[str]  = None
    dispense_date    : date
    quantity         : Decimal
    shift_code       : Optional[str]  = None
    payment_code     : Optional[str]  = None
    doctor_name      : Optional[str]  = None
    note             : Optional[str]  = None
    created_by       : Optional[str]  = None
    created_by_name  : Optional[str]  = None
    created_datetime : datetime

    model_config = ConfigDict(from_attributes = True)


class DispensingResponse(BaseModel):
    id               : UUID
    patient_id       : Optional[UUID] = None
    dispense_date    : date
    department_code  : str
    category_code    : str
    patient_no       : Optional[int]  = None
    patient_name     : str
    age              : Optional[str]  = None
    sex              : Optional[str]  = None
    diagnostic       : Optional[str]  = None
    address_province : Optional[str]  = None
    shift_code       : Optional[str]  = None
    payment_code     : Optional[str]  = None
    doctor_name      : Optional[str]  = None
    duty_chief_name  : Optional[str]  = None
    prepared_by_name : Optional[str]  = None
    note             : Optional[str]  = None
    status_code      : str
    created_datetime : datetime
    items            : List[DispensingItemResponse] = []

    model_config = ConfigDict(from_attributes = True)
