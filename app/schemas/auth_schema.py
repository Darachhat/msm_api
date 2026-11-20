from datetime import datetime
from typing   import Dict, List, Optional
from uuid     import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class DeviceInfo(BaseModel):
    device_id   : Optional[str] = Field(None, max_length = 255)
    device_name : Optional[str] = Field(None, max_length = 255)
    platform    : Optional[str] = Field(None, max_length = 50)  # ios | android | web


class RegisterRequest(BaseModel):
    username        : str                = Field(..., min_length = 3, max_length = 100)
    email           : Optional[EmailStr] = None
    full_name       : str                = Field(..., min_length = 1, max_length = 255)
    full_name_kh    : Optional[str]      = None
    password        : str                = Field(..., min_length = 8, max_length = 128)
    role_code       : str                = "PHARMACIST"
    department_code : Optional[str]      = "SURGICAL_ICU"


class LoginRequest(BaseModel):
    username : str                  = Field(..., min_length = 1, max_length = 100)
    password : str                  = Field(..., min_length = 1, max_length = 128)
    device   : Optional[DeviceInfo] = None


class RefreshTokenBody(BaseModel):
    """Used by mobile clients (X-Client-Type: mobile). Web clients send refresh token via HttpOnly cookie."""

    refresh_token : Optional[str] = Field(None, min_length = 16, max_length = 512)


class AccessTokenResponse(BaseModel):
    """Web clients receive refresh_token=None (stored in HttpOnly cookie).
    Mobile clients (X-Client-Type: mobile) receive the opaque refresh_token for Keychain/Keystore storage."""

    access_token  : str
    refresh_token : Optional[str] = None
    token_type    : str           = "bearer"
    expires_in    : int
    csrf_token    : Optional[str] = None


class ChangePasswordRequest(BaseModel):
    current_password : str = Field(..., min_length = 1, max_length = 128)
    new_password     : str = Field(..., min_length = 8, max_length = 128)


class SessionResponse(BaseModel):
    id                 : UUID
    family_id          : UUID
    device_id          : Optional[str]      = None
    device_name        : Optional[str]      = None
    platform           : Optional[str]      = None
    ip_address         : Optional[str]      = None
    user_agent         : Optional[str]      = None
    created_datetime   : datetime
    last_used_datetime : Optional[datetime] = None
    expires_at         : datetime
    is_current         : bool               = False

    model_config = ConfigDict(from_attributes = True)


class UserResponse(BaseModel):
    id                  : UUID
    username            : str
    email               : Optional[str]                   = None
    full_name           : str
    full_name_kh        : Optional[str]                   = None
    role_code           : str
    department_code     : Optional[str]                   = None
    is_active           : bool
    last_login_datetime : Optional[datetime]              = None
    permissions         : Optional[Dict[str, List[str]]]  = None

    model_config = ConfigDict(from_attributes = True)
