from datetime import date
from decimal  import Decimal
from typing   import List, Optional
import uuid

from sqlalchemy                     import (
    BigInteger
    , Boolean
    , Date
    , ForeignKey
    , Integer
    , Numeric
    , String
    , Text
    , UniqueConstraint
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm                 import Mapped, mapped_column, relationship

from app.models.base_model      import Base
from app.models.base_data_model import MEDICINE_MODEL


class PATIENT_MODEL(Base):
    """data.patient — Patient master record for multi-day dispensing & reports."""

    __tablename__  = "patient"
    __table_args__ = {"schema": "data"}

    id           : Mapped[uuid.UUID]     = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    patient_code : Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    full_name    : Mapped[str]           = mapped_column(String(255), nullable=False, index=True)
    sex          : Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    age          : Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    diagnostic   : Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    pob_province : Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    date_in      : Mapped[date]          = mapped_column(Date, nullable=False, default=date.today)
    note         : Mapped[Optional[str]] = mapped_column(Text, nullable=True)


class PATIENT_DISPENSING_MODEL(Base):
    """data.patient_dispensing — Daily patient dispensing record header."""

    __tablename__  = "patient_dispensing"
    __table_args__ = {"schema": "data"}

    id               : Mapped[uuid.UUID]                         = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    patient_id       : Mapped[Optional[uuid.UUID]]               = mapped_column(UUID(as_uuid=True), ForeignKey("data.patient.id", ondelete="SET NULL"), nullable=True)
    dispense_date    : Mapped[date]                              = mapped_column(Date, nullable=False, index=True)
    department_code  : Mapped[str]                               = mapped_column(String(50), ForeignKey("base_data.department.code"), nullable=False)
    category_code    : Mapped[str]                               = mapped_column(String(50), ForeignKey("base_data.medicine_category.code"), nullable=False)
    patient_no       : Mapped[Optional[int]]                     = mapped_column(Integer, nullable=True)
    patient_name     : Mapped[str]                               = mapped_column(String(255), nullable=False)
    age              : Mapped[Optional[str]]                     = mapped_column(String(20), nullable=True)
    sex              : Mapped[Optional[str]]                     = mapped_column(String(20), nullable=True)
    diagnostic       : Mapped[Optional[str]]                     = mapped_column(Text, nullable=True)
    address_province : Mapped[Optional[str]]                     = mapped_column(String(255), nullable=True)
    doctor_name      : Mapped[Optional[str]]                     = mapped_column(String(255), nullable=True)
    duty_chief_name  : Mapped[Optional[str]]                     = mapped_column(String(255), nullable=True)
    prepared_by_name : Mapped[Optional[str]]                     = mapped_column(String(255), nullable=True)
    note             : Mapped[Optional[str]]                     = mapped_column(Text, nullable=True)
    items            : Mapped[List["PATIENT_DISPENSING_ITEM_MODEL"]] = relationship(
        "PATIENT_DISPENSING_ITEM_MODEL"
        , back_populates = "dispensing"
        , cascade        = "all, delete-orphan"
    )


class PATIENT_DISPENSING_ITEM_MODEL(Base):
    """data.patient_dispensing_item — Normalized medicine quantities per patient dispensing."""

    __tablename__  = "patient_dispensing_item"
    __table_args__ = {"schema": "data"}

    id             : Mapped[uuid.UUID]           = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    dispensing_id  : Mapped[uuid.UUID]           = mapped_column(UUID(as_uuid=True), ForeignKey("data.patient_dispensing.id", ondelete="CASCADE"), nullable=False)
    medicine_id    : Mapped[uuid.UUID]           = mapped_column(UUID(as_uuid=True), ForeignKey("base_data.medicine.id"), nullable=False)
    quantity       : Mapped[Decimal]             = mapped_column(Numeric(12, 2), nullable=False, default=0)
    signature_id   : Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("data.digital_signature.id", ondelete="SET NULL"), nullable=True)
    signature_note : Mapped[Optional[str]]       = mapped_column(String(255), nullable=True)
    note           : Mapped[Optional[str]]       = mapped_column(Text, nullable=True)

    dispensing : Mapped["PATIENT_DISPENSING_MODEL"]   = relationship(
        "PATIENT_DISPENSING_MODEL"
        , back_populates = "items"
    )
    medicine   : Mapped[Optional["MEDICINE_MODEL"]] = relationship("MEDICINE_MODEL", foreign_keys=[medicine_id])


class STOCK_LEDGER_MODEL(Base):
    """data.stock_ledger — Daily opening/income/used/remaining/requested/supplied stock per medicine."""

    __tablename__  = "stock_ledger"
    __table_args__ = (
        UniqueConstraint("stock_date", "department_code", "medicine_id", name="uq_stock_ledger_date_dept_med")
        , {"schema": "data"}
    )

    id              : Mapped[uuid.UUID]     = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    stock_date      : Mapped[date]          = mapped_column(Date, nullable=False, index=True)
    department_code : Mapped[str]           = mapped_column(
        String(50)
        , ForeignKey("base_data.department.code")
        , nullable = False
    )
    medicine_id     : Mapped[uuid.UUID]     = mapped_column(
        UUID(as_uuid=True)
        , ForeignKey("base_data.medicine.id")
        , nullable = False
    )
    opening_qty     : Mapped[Decimal]       = mapped_column(Numeric(12, 2), nullable=False, default=0)
    added_qty       : Mapped[Decimal]       = mapped_column(Numeric(12, 2), nullable=False, default=0)
    used_qty        : Mapped[Decimal]       = mapped_column(Numeric(12, 2), nullable=False, default=0)
    remaining_qty   : Mapped[Decimal]       = mapped_column(Numeric(12, 2), nullable=False, default=0)
    requested_qty   : Mapped[Decimal]       = mapped_column(Numeric(12, 2), nullable=False, default=0)
    supplied_qty    : Mapped[Decimal]       = mapped_column(Numeric(12, 2), nullable=False, default=0)
    note            : Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    medicine : Mapped[Optional["MEDICINE_MODEL"]] = relationship("MEDICINE_MODEL", foreign_keys=[medicine_id])


class STOCK_BATCH_MODEL(Base):
    """data.stock_batch — Stock-in batches with input_date and optional expire_date."""

    __tablename__  = "stock_batch"
    __table_args__ = {"schema": "data"}

    id              : Mapped[uuid.UUID]      = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    department_code : Mapped[str]            = mapped_column(String(50), ForeignKey("base_data.department.code"), nullable=False)
    medicine_id     : Mapped[uuid.UUID]      = mapped_column(UUID(as_uuid=True), ForeignKey("base_data.medicine.id"), nullable=False)
    batch_no        : Mapped[Optional[str]]  = mapped_column(String(100), nullable=True)
    total_qty       : Mapped[Decimal]        = mapped_column(Numeric(12, 2), nullable=False, default=0)
    remaining_qty   : Mapped[Decimal]        = mapped_column(Numeric(12, 2), nullable=False, default=0)
    input_date      : Mapped[date]           = mapped_column(Date, nullable=False, default=date.today)
    expire_date     : Mapped[Optional[date]] = mapped_column(Date, nullable=True, index=True)
    note            : Mapped[Optional[str]]  = mapped_column(Text, nullable=True)

    medicine : Mapped[Optional["MEDICINE_MODEL"]] = relationship("MEDICINE_MODEL", foreign_keys=[medicine_id])


class FILE_OBJECT_MODEL(Base):
    """data.file_object — OSM-style file registry backed by Cloudflare R2."""

    __tablename__  = "file_object"
    __table_args__ = {"schema": "data"}

    id             : Mapped[uuid.UUID]     = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    path_code      : Mapped[str]           = mapped_column(String(64), nullable=False, unique=True, index=True)
    title          : Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    filename       : Mapped[str]           = mapped_column(String(255), nullable=False)
    ext            : Mapped[str]           = mapped_column(String(20), nullable=False)
    mime_type      : Mapped[str]           = mapped_column(String(150), nullable=False)
    size           : Mapped[int]           = mapped_column(BigInteger, nullable=False, default=0)
    r2_bucket      : Mapped[str]           = mapped_column(String(150), nullable=False)
    r2_object_key  : Mapped[str]           = mapped_column(String(500), nullable=False)
    module         : Mapped[str]           = mapped_column(String(100), nullable=False, default="reports")
    preview_url    : Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    download_url   : Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    accessed_count : Mapped[int]           = mapped_column(Integer, nullable=False, default=0)


class DIGITAL_SIGNATURE_MODEL(Base):
    """data.digital_signature — Saved digital signatures for doctors/nurses/staff."""

    __tablename__  = "digital_signature"
    __table_args__ = {"schema": "data"}

    id             : Mapped[uuid.UUID]           = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id        : Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True)
        , ForeignKey("auth.user.id", ondelete="SET NULL")
        , nullable = True
    )
    signer_name    : Mapped[str]                 = mapped_column(String(255), nullable=False)
    signer_role    : Mapped[Optional[str]]       = mapped_column(String(100), nullable=True)
    file_object_id : Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True)
        , ForeignKey("data.file_object.id", ondelete="SET NULL")
        , nullable = True
    )
    signature_data : Mapped[Optional[str]]       = mapped_column(Text, nullable=True)
    is_default     : Mapped[bool]                = mapped_column(Boolean, nullable=False, default=False)

    file_object : Mapped[Optional["FILE_OBJECT_MODEL"]] = relationship(
        "FILE_OBJECT_MODEL"
        , foreign_keys = [file_object_id]
    )


class REPORT_EXPORT_MODEL(Base):
    """data.report_export — Tracks generated Excel reports and links to data.file_object."""

    __tablename__  = "report_export"
    __table_args__ = {"schema": "data"}

    id               : Mapped[uuid.UUID]           = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    report_type_code : Mapped[str]                 = mapped_column(
        String(50)
        , ForeignKey("base_data.report_type.code")
        , nullable = False
    )
    department_code  : Mapped[str]                 = mapped_column(
        String(50)
        , ForeignKey("base_data.department.code")
        , nullable = False
    )
    category_code    : Mapped[Optional[str]]       = mapped_column(
        String(50)
        , ForeignKey("base_data.medicine_category.code")
        , nullable = True
    )
    medicine_id      : Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True)
        , ForeignKey("base_data.medicine.id")
        , nullable = True
    )
    start_date       : Mapped[date]                = mapped_column(Date, nullable=False)
    end_date         : Mapped[date]                = mapped_column(Date, nullable=False)
    file_object_id   : Mapped[uuid.UUID]           = mapped_column(
        UUID(as_uuid=True)
        , ForeignKey("data.file_object.id")
        , nullable = False
    )
    signers_json     : Mapped[Optional[dict]]      = mapped_column(JSONB, nullable=True)

    file_object : Mapped[Optional["FILE_OBJECT_MODEL"]] = relationship(
        "FILE_OBJECT_MODEL"
        , foreign_keys = [file_object_id]
    )
