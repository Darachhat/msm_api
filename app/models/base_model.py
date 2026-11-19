from datetime import datetime
from typing   import Optional

from sqlalchemy     import DateTime, String
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from app.core.enum import STATUS_CODE_ENUM


class Base(DeclarativeBase):
    status_code      : Mapped[str]                 = mapped_column(String(20), nullable = False, default = STATUS_CODE_ENUM.ACTIVE.value)
    created_datetime : Mapped[datetime]            = mapped_column(DateTime, nullable = False, default = datetime.utcnow)
    updated_datetime : Mapped[Optional[datetime]]  = mapped_column(DateTime, nullable = True, onupdate = datetime.utcnow)
    deleted_datetime : Mapped[Optional[datetime]]  = mapped_column(DateTime, nullable = True)
    created_by       : Mapped[Optional[str]]       = mapped_column(String(100), nullable = True)
    updated_by       : Mapped[Optional[str]]       = mapped_column(String(100), nullable = True)
    deleted_by       : Mapped[Optional[str]]       = mapped_column(String(100), nullable = True)
