from datetime import datetime
from typing   import Optional
from uuid     import UUID

from pydantic import ConfigDict, BaseModel, Field


class SignatureCreate(BaseModel):
    signer_name    : str           = Field(..., min_length = 1, max_length = 255)
    signer_role    : Optional[str] = None  # DOCTOR | NURSE | PHARMACIST | DUTY_CHIEF | DIRECTOR
    signature_data : Optional[str] = Field(None, max_length = 3_000_000)  # Base64 PNG/SVG data URL
    is_default     : bool          = False


class SignatureResponse(BaseModel):
    id               : UUID
    user_id          : Optional[UUID] = None
    signer_name      : str
    signer_role      : Optional[str]  = None
    signature_data   : Optional[str]  = None
    preview_url      : Optional[str]  = None
    is_default       : bool
    created_datetime : datetime

    model_config = ConfigDict(from_attributes = True)
