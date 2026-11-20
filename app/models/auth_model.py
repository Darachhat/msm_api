from typing import Any, Optional
import uuid

from sqlalchemy                     import ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm                 import Mapped, mapped_column

from app.models.base_model import Base


class SYSTEM_MODEL(Base):
    """auth.system — Registered internal/external systems for M2M authentication."""

    __tablename__  = "system"
    __table_args__ = {"schema": "auth"}

    id            : Mapped[uuid.UUID]     = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    code          : Mapped[str]           = mapped_column(String(100), nullable=False, unique=True)
    name          : Mapped[str]           = mapped_column(String(255), nullable=False)
    description   : Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    base_url      : Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    scope         : Mapped[str]           = mapped_column(String(50), nullable=False, default="INTERNAL")
    metadata_json : Mapped[Optional[Any]] = mapped_column(JSONB, nullable=True)


class SYSTEM_CREDENTIAL_MODEL(Base):
    """auth.system_credential — Maps a system to its inbound/outbound auth type."""

    __tablename__  = "system_credential"
    __table_args__ = {"schema": "auth"}

    id             : Mapped[uuid.UUID]     = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    system_code    : Mapped[str]           = mapped_column(
        String(100)
        , ForeignKey("auth.system.code", ondelete="CASCADE")
        , nullable = False
    )
    traffic_type   : Mapped[str]           = mapped_column(String(20), nullable=False)  # INBOUND | OUTBOUND
    auth_type_code : Mapped[str]           = mapped_column(String(50), nullable=False)  # API_KEY | BEARER | BASIC
    description    : Mapped[Optional[str]] = mapped_column(Text, nullable=True)


class CREDENTIAL_API_KEY_MODEL(Base):
    """auth.credential_api_key — API key credentials for inbound/outbound system auth."""

    __tablename__  = "credential_api_key"
    __table_args__ = {"schema": "auth"}

    id           : Mapped[uuid.UUID]     = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    system_code  : Mapped[str]           = mapped_column(
        String(100)
        , ForeignKey("auth.system.code", ondelete="CASCADE")
        , nullable = False
    )
    traffic_type : Mapped[str]           = mapped_column(String(20), nullable=False)
    key_location : Mapped[str]           = mapped_column(String(20), nullable=False, default="header")
    key_name     : Mapped[str]           = mapped_column(String(100), nullable=False, default="X-API-Key")
    key_value    : Mapped[str]           = mapped_column(Text, nullable=False)
    description  : Mapped[Optional[str]] = mapped_column(Text, nullable=True)


class CREDENTIAL_BEARER_MODEL(Base):
    """auth.credential_bearer — Static bearer token credentials for inbound/outbound system auth."""

    __tablename__  = "credential_bearer"
    __table_args__ = {"schema": "auth"}

    id           : Mapped[uuid.UUID]     = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    system_code  : Mapped[str]           = mapped_column(
        String(100)
        , ForeignKey("auth.system.code", ondelete="CASCADE")
        , nullable = False
    )
    traffic_type : Mapped[str]           = mapped_column(String(20), nullable=False)
    header_name  : Mapped[str]           = mapped_column(String(100), nullable=False, default="Authorization")
    token_prefix : Mapped[str]           = mapped_column(String(50), nullable=False, default="Bearer")
    token_value  : Mapped[str]           = mapped_column(Text, nullable=False)
    description  : Mapped[Optional[str]] = mapped_column(Text, nullable=True)


class CREDENTIAL_BASIC_MODEL(Base):
    """auth.credential_basic — HTTP Basic credentials for inbound/outbound system auth."""

    __tablename__  = "credential_basic"
    __table_args__ = {"schema": "auth"}

    id           : Mapped[uuid.UUID]     = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    system_code  : Mapped[str]           = mapped_column(
        String(100)
        , ForeignKey("auth.system.code", ondelete="CASCADE")
        , nullable = False
    )
    traffic_type : Mapped[str]           = mapped_column(String(20), nullable=False)
    username     : Mapped[str]           = mapped_column(String(255), nullable=False)
    password     : Mapped[str]           = mapped_column(Text, nullable=False)
    description  : Mapped[Optional[str]] = mapped_column(Text, nullable=True)
