from datetime import datetime
from typing   import Any, Optional

from app.schemas.base_schema import Base


class SYSTEM_LOG_DATA(Base):
    """Typed schema for system_log entries written to track.system_log."""

    # Required fields
    traffic_type       : str
    request_method     : str
    request_endpoint   : str
    requested_datetime : datetime
    status_code        : str
    created_datetime   : datetime

    # Request fields
    system_code          : Optional[str] = None
    channel              : Optional[str] = None
    request_netloc       : Optional[str] = None
    request_content_type : Optional[str] = None
    request_user_agent   : Optional[str] = None
    request_headers      : Optional[Any] = None
    request_body         : Optional[Any] = None
    client_ip            : Optional[str] = None

    # Response fields
    response_code     : Optional[int]      = None
    response_headers  : Optional[Any]      = None
    response_body     : Optional[Any]      = None
    response_duration : Optional[float]    = None
    response_datetime : Optional[datetime] = None

    # Tracking
    client_log_id : Optional[str] = None
