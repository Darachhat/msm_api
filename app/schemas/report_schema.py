from datetime import date, datetime
from decimal  import Decimal
from typing   import Any, Dict, List, Optional
from uuid     import UUID

from pydantic import BaseModel, ConfigDict, Field


class ReportGenerateRequest(BaseModel):
    report_type_code : str  # DAILY_USAGE | DAILY_STOCK | WEEKLY_USAGE_REQUEST | NARCOTIC_USAGE | PATIENT_USAGE
    period           : str                      = "DAILY"  # DAILY | WEEKLY | MONTHLY
    department_code  : str                      = "SURGICAL_ICU"
    category_code    : Optional[str]            = None  # TABLET | INJECTION
    medicine_id      : Optional[UUID]           = None  # Optional filter for NARCOTIC_USAGE
    patient_id       : Optional[UUID]           = None  # Optional filter for PATIENT_USAGE
    start_date       : date
    end_date         : Optional[date]           = None  # Auto-calculated from period if omitted
    signers          : Optional[Dict[str, str]] = None


class FileObjectResponse(BaseModel):
    id               : UUID
    path_code        : str
    title            : Optional[str] = None
    filename         : str
    ext              : str
    mime_type        : str
    size             : int
    preview_url      : Optional[str] = None
    download_url     : Optional[str] = None
    accessed_count   : int
    created_datetime : datetime

    model_config = ConfigDict(from_attributes = True)


class ReportExportResponse(BaseModel):
    id               : UUID
    report_type_code : str
    department_code  : str
    category_code    : Optional[str]                = None
    medicine_id      : Optional[UUID]               = None
    start_date       : date
    end_date         : date
    signers_json     : Optional[Dict[str, Any]]     = None
    created_datetime : datetime
    file_object      : Optional[FileObjectResponse] = None

    model_config = ConfigDict(from_attributes = True)


# --- JSON Report Data Schemas (consumed by msm_front report screens) ---

class ReportMedicineRef(BaseModel):
    id            : UUID
    code          : str
    name          : str
    form_code     : str
    form_name     : Optional[str] = None
    dosage        : Optional[str] = None
    category_code : str
    is_narcotic   : bool          = False
    sort_order    : int           = 0
    status_code   : str           = "ACTIVE"


class StockSummaryRow(BaseModel):
    medicine      : ReportMedicineRef
    opening       : Decimal            = Decimal("0")
    received      : Decimal            = Decimal("0")
    daily_used    : Dict[str, Decimal] = {}
    used          : Decimal            = Decimal("0")
    write_off     : Decimal            = Decimal("0")
    closing       : Decimal            = Decimal("0")
    requested_qty : Optional[Decimal]  = None
    supplied_qty  : Optional[Decimal]  = None


class StockSummaryReportResponse(BaseModel):
    start_date : date
    end_date   : date
    days       : List[str]             = []
    rows       : List[StockSummaryRow] = []


class ReportRequestItemInput(BaseModel):
    medicine_id   : UUID
    requested_qty : Decimal = Field(default = Decimal("0"), ge = 0)
    supplied_qty  : Decimal = Field(default = Decimal("0"), ge = 0)


class ReportRequestsUpsert(BaseModel):
    department_code : str                          = "SURGICAL_ICU"
    start_date      : date
    end_date        : date
    items           : List[ReportRequestItemInput] = []


class DailySheetRow(BaseModel):
    patient_id   : Optional[UUID]     = None
    patient_code : Optional[str]      = None
    patient_name : str
    sex          : Optional[str]      = None
    age          : Optional[str]      = None
    diagnostic   : Optional[str]      = None
    province     : Optional[str]      = None
    date_in      : Optional[date]     = None
    quantities   : Dict[str, Decimal] = {}
    first_at     : Optional[datetime] = None


class DailySheetReportResponse(BaseModel):
    start_date : date
    end_date   : date
    columns    : List[ReportMedicineRef] = []
    rows       : List[DailySheetRow]     = []
    totals     : Dict[str, Decimal]      = {}


class MedicineUsagePatientEntry(BaseModel):
    patient_id   : Optional[UUID] = None
    patient_name : str
    sex          : Optional[str]  = None
    age          : Optional[str]  = None
    quantity     : Decimal        = Decimal("0")
    times        : int            = 0


class MedicineUsageReportItem(BaseModel):
    medicine      : ReportMedicineRef
    total         : Decimal                         = Decimal("0")
    patient_count : int                             = 0
    patients      : List[MedicineUsagePatientEntry] = []


class MedicineUsageReportResponse(BaseModel):
    start_date : date
    end_date   : date
    items      : List[MedicineUsageReportItem] = []
