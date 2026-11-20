from typing import Optional
from uuid   import UUID

from pydantic import ConfigDict, BaseModel, Field


class MedicineCreate(BaseModel):
    code            : str           = Field(..., max_length = 100)
    name            : str           = Field(..., max_length = 255)
    category_code   : str           = Field(..., max_length = 50)
    form_code       : str           = Field(..., max_length = 50)
    dosage          : Optional[str] = None
    unit_label      : Optional[str] = None
    is_narcotic     : bool          = False
    narcotic_doc_no : Optional[str] = None
    sort_order      : int           = 0


class MedicineUpdate(BaseModel):
    name            : Optional[str]  = None
    category_code   : Optional[str]  = None
    form_code       : Optional[str]  = None
    dosage          : Optional[str]  = None
    unit_label      : Optional[str]  = None
    is_narcotic     : Optional[bool] = None
    narcotic_doc_no : Optional[str]  = None
    sort_order      : Optional[int]  = None
    status_code     : Optional[str]  = None


class MedicineResponse(BaseModel):
    id              : UUID
    code            : str
    name            : str
    category_code   : str
    form_code       : str
    dosage          : Optional[str] = None
    unit_label      : Optional[str] = None
    is_narcotic     : bool
    narcotic_doc_no : Optional[str] = None
    sort_order      : int
    status_code     : str

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
