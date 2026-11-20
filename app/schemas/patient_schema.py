from datetime import date, datetime
from decimal  import Decimal
from typing   import List, Optional
from uuid     import UUID

from pydantic import ConfigDict, BaseModel, Field


class PatientCreate(BaseModel):
    patient_code : Optional[str] = None
    full_name    : str           = Field(..., min_length = 1, max_length = 255)
    sex          : Optional[str] = None
    age          : Optional[str] = None
    diagnostic   : Optional[str] = None
    pob_province : Optional[str] = None
    date_in      : date          = Field(default_factory = date.today)
    note         : Optional[str] = None


class PatientUpdate(BaseModel):
    patient_code : Optional[str]  = None
    full_name    : Optional[str]  = None
    sex          : Optional[str]  = None
    age          : Optional[str]  = None
    diagnostic   : Optional[str]  = None
    pob_province : Optional[str]  = None
    date_in      : Optional[date] = None
    note         : Optional[str]  = None
    status_code  : Optional[str]  = None


class PatientResponse(BaseModel):
    id               : UUID
    patient_code     : Optional[str] = None
    full_name        : str
    sex              : Optional[str] = None
    age              : Optional[str] = None
    diagnostic       : Optional[str] = None
    pob_province     : Optional[str] = None
    date_in          : date
    note             : Optional[str] = None
    status_code      : str
    created_datetime : datetime

    model_config = ConfigDict(from_attributes = True)


class PatientMedicineUsageItem(BaseModel):
    medicine_id    : UUID
    medicine_code  : str
    medicine_name  : str
    category_code  : str
    form_code      : str
    dosage         : Optional[str] = None
    total_quantity : Decimal


class PatientUsageReportResponse(BaseModel):
    patient_id   : Optional[UUID] = None
    patient_name : str
    sex          : Optional[str]  = None
    age          : Optional[str]  = None
    diagnostic   : Optional[str]  = None
    pob_province : Optional[str]  = None
    date_in      : Optional[date] = None
    start_date   : date
    end_date     : date
    medicines    : List[PatientMedicineUsageItem] = []
