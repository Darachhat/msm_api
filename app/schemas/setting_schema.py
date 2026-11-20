from datetime import datetime
from typing   import List, Optional
from uuid     import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class ServiceModuleResponse(BaseModel):
    id          : UUID
    code        : str
    name        : str
    description : Optional[str] = None
    sort_order  : int

    model_config = ConfigDict(from_attributes = True)


class RolePermissionInput(BaseModel):
    service_code : str
    can_read     : bool = False
    can_write    : bool = False
    can_update   : bool = False
    can_delete   : bool = False


class RolePermissionResponse(BaseModel):
    id           : UUID
    role_code    : str
    service_code : str
    can_read     : bool
    can_write    : bool
    can_update   : bool
    can_delete   : bool

    model_config = ConfigDict(from_attributes = True)


class RoleCreate(BaseModel):
    code        : Optional[str]             = Field(None, min_length = 2, max_length = 50)
    name        : str                       = Field(..., min_length = 1, max_length = 150)
    description : Optional[str]             = None
    permissions : List[RolePermissionInput] = []


class RoleUpdate(BaseModel):
    name        : Optional[str]                       = Field(None, min_length = 1, max_length = 150)
    description : Optional[str]                       = None
    permissions : Optional[List[RolePermissionInput]] = None


class RoleResponse(BaseModel):
    id          : UUID
    code        : str
    name        : str
    description : Optional[str]                = None
    status_code : str
    user_count  : int                          = 0
    permissions : List[RolePermissionResponse] = []

    model_config = ConfigDict(from_attributes = True)


class UserCreateByAdmin(BaseModel):
    username        : str                = Field(..., min_length = 3, max_length = 100)
    email           : Optional[EmailStr] = None
    full_name       : str                = Field(..., min_length = 1, max_length = 255)
    full_name_kh    : Optional[str]      = None
    password        : str                = Field(..., min_length = 8, max_length = 128)
    role_code       : str                = "PHARMACIST"
    department_code : Optional[str]      = "SURGICAL_ICU"


class UserUpdateByAdmin(BaseModel):
    email           : Optional[EmailStr] = None
    full_name       : Optional[str]      = None
    full_name_kh    : Optional[str]      = None
    password        : Optional[str]      = Field(None, min_length = 8, max_length = 128)
    role_code       : Optional[str]      = None
    department_code : Optional[str]      = None
    is_active       : Optional[bool]     = None
    status_code     : Optional[str]      = None


class LoginHistoryResponse(BaseModel):
    id             : UUID
    user_id        : Optional[UUID] = None
    username       : str
    ip_address     : Optional[str]  = None
    user_agent     : Optional[str]  = None
    login_status   : str
    failure_reason : Optional[str]  = None
    login_datetime : datetime

    model_config = ConfigDict(from_attributes = True)
