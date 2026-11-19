from datetime import datetime
from typing   import Optional
import uuid

from sqlalchemy                     import Boolean, DateTime, ForeignKey, SmallInteger, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm                 import Mapped, mapped_column, relationship

from app.core.enum         import ROLE_CODE_ENUM
from app.models.base_model import Base


class ROLE_MODEL(Base):
    """auth.role — Role definitions (ADMIN, PHARMACIST, NURSE, VIEWER)."""

    __tablename__  = "role"
    __table_args__ = {"schema": "auth"}

    id           : Mapped[uuid.UUID]           = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    code         : Mapped[str]                 = mapped_column(String(50), nullable=False, unique=True)
    name         : Mapped[str]                 = mapped_column(String(150), nullable=False)
    description  : Mapped[Optional[str]]       = mapped_column(Text, nullable=True)
    translate_id : Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True)
        , ForeignKey("base_data.translate.id")
        , nullable = True
    )


class USER_MODEL(Base):
    """auth.user — Staff / API user accounts for JWT authentication."""

    __tablename__  = "user"
    __table_args__ = {"schema": "auth"}

    id                  : Mapped[uuid.UUID]           = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    username            : Mapped[str]                 = mapped_column(String(100), nullable=False, unique=True)
    email               : Mapped[Optional[str]]       = mapped_column(String(255), nullable=True, unique=True)
    full_name           : Mapped[str]                 = mapped_column(String(255), nullable=False)
    full_name_kh        : Mapped[Optional[str]]       = mapped_column(String(255), nullable=True)
    password_hash       : Mapped[str]                 = mapped_column(Text, nullable=False)
    role_code           : Mapped[str]                 = mapped_column(
        String(50)
        , ForeignKey("auth.role.code")
        , nullable = False
        , default  = ROLE_CODE_ENUM.PHARMACIST.value
    )
    department_code     : Mapped[Optional[str]]       = mapped_column(
        String(50)
        , ForeignKey("base_data.department.code")
        , nullable = True
    )
    is_active           : Mapped[bool]                = mapped_column(Boolean, nullable=False, default=True)
    last_login_datetime : Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    role : Mapped[Optional["ROLE_MODEL"]] = relationship("ROLE_MODEL", foreign_keys=[role_code])


class REFRESH_TOKEN_MODEL(Base):
    """auth.refresh_token — Tracks issued refresh tokens for revocation."""

    __tablename__  = "refresh_token"
    __table_args__ = {"schema": "auth"}

    id         : Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id    : Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True)
        , ForeignKey("auth.user.id")
        , nullable = False
    )
    jti        : Mapped[str]       = mapped_column(String(100), nullable=False, unique=True)
    expires_at : Mapped[datetime]  = mapped_column(DateTime, nullable=False)
    revoked    : Mapped[bool]      = mapped_column(Boolean, nullable=False, default=False)


class SERVICE_MODULE_MODEL(Base):
    """auth.service_module — Controllable services/modules for RBAC (DASHBOARD, PATIENT, STOCK, etc.)."""

    __tablename__  = "service_module"
    __table_args__ = {"schema": "auth"}

    id          : Mapped[uuid.UUID]     = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    code        : Mapped[str]           = mapped_column(String(50), nullable=False, unique=True)
    name        : Mapped[str]           = mapped_column(String(150), nullable=False)
    description : Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    sort_order  : Mapped[int]           = mapped_column(SmallInteger, nullable=False, default=0)


class ROLE_PERMISSION_MODEL(Base):
    """auth.role_permission — Per-role, per-service Read/Write/Update/Delete flags."""

    __tablename__  = "role_permission"
    __table_args__ = {"schema": "auth"}

    id           : Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    role_code    : Mapped[str]       = mapped_column(
        String(50)
        , ForeignKey("auth.role.code", ondelete="CASCADE")
        , nullable = False
    )
    service_code : Mapped[str]       = mapped_column(
        String(50)
        , ForeignKey("auth.service_module.code", ondelete="CASCADE")
        , nullable = False
    )
    can_read     : Mapped[bool]      = mapped_column(Boolean, nullable=False, default=False)
    can_write    : Mapped[bool]      = mapped_column(Boolean, nullable=False, default=False)
    can_update   : Mapped[bool]      = mapped_column(Boolean, nullable=False, default=False)
    can_delete   : Mapped[bool]      = mapped_column(Boolean, nullable=False, default=False)

    service : Mapped[Optional["SERVICE_MODULE_MODEL"]] = relationship(
        "SERVICE_MODULE_MODEL"
        , foreign_keys = [service_code]
    )


class LOGIN_HISTORY_MODEL(Base):
    """auth.login_history — Audit log of user login attempts."""

    __tablename__  = "login_history"
    __table_args__ = {"schema": "auth"}

    id             : Mapped[uuid.UUID]           = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id        : Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True)
        , ForeignKey("auth.user.id", ondelete="SET NULL")
        , nullable = True
    )
    username       : Mapped[str]                 = mapped_column(String(100), nullable=False)
    ip_address     : Mapped[Optional[str]]       = mapped_column(String(100), nullable=True)
    user_agent     : Mapped[Optional[str]]       = mapped_column(Text, nullable=True)
    login_status   : Mapped[str]                 = mapped_column(String(20), nullable=False)  # SUCCESS | FAILED
    failure_reason : Mapped[Optional[str]]       = mapped_column(String(255), nullable=True)
    login_datetime : Mapped[datetime]            = mapped_column(DateTime, nullable=False, default=datetime.utcnow)
