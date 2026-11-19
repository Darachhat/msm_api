from datetime import datetime
from typing   import Optional
from uuid     import UUID

from pydantic import BaseModel, EmailStr, Field


class RegisterRequest(BaseModel):
    username        : str                = Field(..., min_length = 3, max_length = 100)
    email           : Optional[EmailStr] = None
    full_name       : str                = Field(..., min_length = 1, max_length = 255)
    full_name_kh    : Optional[str]      = None
    password        : str                = Field(..., min_length = 6, max_length = 128)
    role_code       : str                = "PHARMACIST"
    department_code : Optional[str]      = "SURGICAL_ICU"


class LoginRequest(BaseModel):
    username : str
    password : str


class RefreshTokenRequest(BaseModel):
    refresh_token : str


class TokenResponse(BaseModel):
    access_token  : str
    refresh_token : str
    token_type    : str = "bearer"
    expires_in    : int


class UserResponse(BaseModel):
    id                  : UUID
    username            : str
    email               : Optional[str]      = None
    full_name           : str
    full_name_kh        : Optional[str]      = None
    role_code           : str
    department_code     : Optional[str]      = None
    is_active           : bool
    last_login_datetime : Optional[datetime] = None

    class Config:
        from_attributes = True
