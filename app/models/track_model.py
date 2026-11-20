from datetime import datetime
from decimal  import Decimal
from typing   import Any, Optional
import uuid

from sqlalchemy                     import DateTime, ForeignKey, Integer, Numeric, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm                 import Mapped, mapped_column

from app.models.base_model import Base


class SYSTEM_LOG_MODEL(Base):
    """track.system_log — Inbound and outbound API audit log."""

    __tablename__  = "system_log"
    __table_args__ = {"schema": "track"}

    id                   : Mapped[uuid.UUID]          = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    client_log_id        : Mapped[Optional[str]]      = mapped_column(String(40), nullable=True)

    traffic_type         : Mapped[Optional[str]]      = mapped_column(String(20), nullable=True)   # INBOUND | OUTBOUND
    system_code          : Mapped[Optional[str]]      = mapped_column(String(100), nullable=True)
    channel              : Mapped[Optional[str]]      = mapped_column(String(50), nullable=True)   # API | SYSTEM

    request_method       : Mapped[str]                = mapped_column(String(10), nullable=False)
    request_endpoint     : Mapped[str]                = mapped_column(Text, nullable=False)
    request_netloc       : Mapped[Optional[str]]      = mapped_column(String(255), nullable=True)  # scheme://host:port
    request_content_type : Mapped[Optional[str]]      = mapped_column(String(255), nullable=True)
    request_user_agent   : Mapped[Optional[str]]      = mapped_column(Text, nullable=True)
    request_headers      : Mapped[Optional[Any]]      = mapped_column(JSONB, nullable=True)        # sensitive values redacted
    request_body         : Mapped[Optional[Any]]      = mapped_column(JSONB, nullable=True)
    requested_datetime   : Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    client_ip            : Mapped[Optional[str]]      = mapped_column(String(50), nullable=True)

    response_code        : Mapped[Optional[int]]      = mapped_column(Integer, nullable=True)
    response_headers     : Mapped[Optional[Any]]      = mapped_column(JSONB, nullable=True)
    response_body        : Mapped[Optional[Any]]      = mapped_column(JSONB, nullable=True)
    response_duration    : Mapped[Optional[Decimal]]  = mapped_column(Numeric, nullable=True)      # seconds
    response_datetime    : Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)


class AUTH_AUDIT_LOG_MODEL(Base):
    """track.auth_audit_log — Audit trail for login, refresh, reuse detection, logout, and password events."""

    __tablename__  = "auth_audit_log"
    __table_args__ = {"schema": "track"}

    id            : Mapped[uuid.UUID]           = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id       : Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True)
        , ForeignKey("data.user.id", ondelete="SET NULL")
        , nullable = True
    )
    username      : Mapped[Optional[str]]       = mapped_column(String(100), nullable=True)
    event_type    : Mapped[str]                 = mapped_column(String(50), nullable=False)
    event_status  : Mapped[str]                 = mapped_column(String(20), nullable=False)  # SUCCESS | FAILED | ALERT
    ip_address    : Mapped[Optional[str]]       = mapped_column(String(100), nullable=True)
    user_agent    : Mapped[Optional[str]]       = mapped_column(Text, nullable=True)
    detail        : Mapped[Optional[str]]       = mapped_column(Text, nullable=True)
    metadata_json : Mapped[Optional[Any]]       = mapped_column(JSONB, nullable=True)
