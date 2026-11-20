from datetime import date, datetime
from decimal  import Decimal
from typing   import List, Optional
from uuid     import UUID

from pydantic import BaseModel, ConfigDict, Field


class PatientCreate(BaseModel):
    patient_code : Optional[str]  = None
    full_name    : str            = Field(..., min_length = 1, max_length = 255)
    sex          : Optional[str]  = None
    age          : Optional[str]  = None
    diagnostic   : Optional[str]  = None
    pob_province : Optional[str]  = None
    date_in      : date           = Field(default_factory = date.today)
    date_out     : Optional[date] = None
    note         : Optional[str]  = None


class PatientUpdate(BaseModel):
    patient_code : Optional[str]  = None
    full_name    : Optional[str]  = None
    sex          : Optional[str]  = None
    age          : Optional[str]  = None
    diagnostic   : Optional[str]  = None
    pob_province : Optional[str]  = None
    date_in      : Optional[date] = None
    date_out     : Optional[date] = None
    note         : Optional[str]  = None
    status_code  : Optional[str]  = None


class PatientResponse(BaseModel):
    id               : UUID
    patient_code     : Optional[str]      = None
    full_name        : str
    sex              : Optional[str]      = None
    age              : Optional[str]      = None
    diagnostic       : Optional[str]      = None
    pob_province     : Optional[str]      = None
    date_in          : date
    date_out         : Optional[date]     = None
    admission_status : str                = "ADMITTED"
    note             : Optional[str]      = None
    status_code      : str
    created_datetime : datetime
    updated_datetime : Optional[datetime] = None

    model_config = ConfigDict(from_attributes = True)


class PatientMedicineUsageItem(BaseModel):
    medicine_id    : UUID
    medicine_code  : str
    medicine_name  : str
    category_code  : str
    is_narcotic    : bool          = False
    form_code      : str
    dosage         : Optional[str] = None
    sort_order     : int           = 0
    total_quantity : Decimal
    days_count     : int           = 0


class PatientUsageReportResponse(BaseModel):
    patient_id   : Optional[UUID] = None
    patient_code : Optional[str]  = None
    patient_name : str
    sex          : Optional[str]  = None
    age          : Optional[str]  = None
    diagnostic   : Optional[str]  = None
    pob_province : Optional[str]  = None
    date_in      : Optional[date] = None
    start_date   : date
    end_date     : date
    medicines    : List[PatientMedicineUsageItem] = []
