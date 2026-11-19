from enum import Enum


class RESPONSE_STATUS_ENUM(int, Enum):
    SUCCESS = 1
    FAILED  = 0


class STATUS_CODE_ENUM(str, Enum):
    ACTIVE   = "ACTIVE"
    INACTIVE = "INACTIVE"
    DRAFT    = "DRAFT"
    ARCHIVED = "ARCHIVED"
    DELETED  = "DELETED"


class ROLE_CODE_ENUM(str, Enum):
    ADMIN      = "ADMIN"
    PHARMACIST = "PHARMACIST"
    NURSE      = "NURSE"
    VIEWER     = "VIEWER"


class SERVICE_MODULE_ENUM(str, Enum):
    DASHBOARD  = "DASHBOARD"
    PATIENT    = "PATIENT"
    STOCK      = "STOCK"
    DISPENSING = "DISPENSING"
    REPORT     = "REPORT"
    SETTING    = "SETTING"


class PERMISSION_ACTION_ENUM(str, Enum):
    READ   = "READ"
    WRITE  = "WRITE"
    UPDATE = "UPDATE"
    DELETE = "DELETE"


class MEDICINE_CATEGORY_ENUM(str, Enum):
    TABLET    = "TABLET"
    INJECTION = "INJECTION"


class REPORT_TYPE_ENUM(str, Enum):
    DAILY_USAGE          = "DAILY_USAGE"
    DAILY_STOCK          = "DAILY_STOCK"
    WEEKLY_USAGE_REQUEST = "WEEKLY_USAGE_REQUEST"
    NARCOTIC_USAGE       = "NARCOTIC_USAGE"
    PATIENT_USAGE        = "PATIENT_USAGE"


class REPORT_PERIOD_ENUM(str, Enum):
    DAILY   = "DAILY"
    WEEKLY  = "WEEKLY"
    MONTHLY = "MONTHLY"


class SEX_ENUM(str, Enum):
    MALE   = "M"
    FEMALE = "F"
    OTHER  = "O"


class TRAFFIC_TYPE_ENUM(str, Enum):
    INBOUND  = "INBOUND"
    OUTBOUND = "OUTBOUND"


class CHANNEL_ENUM(str, Enum):
    API    = "API"
    SYSTEM = "SYSTEM"
