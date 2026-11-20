from datetime import date, datetime
from typing   import Any, Dict, Optional
from uuid     import UUID

from pydantic import ConfigDict, BaseModel


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
