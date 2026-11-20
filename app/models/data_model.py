from datetime import date, datetime
from decimal  import Decimal
from typing   import List, Optional
import uuid

from sqlalchemy                     import (
    BigInteger
    , Boolean
    , Date
    , DateTime
    , ForeignKey
    , Integer
    , Numeric
    , String
    , Text
    , UniqueConstraint
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm                 import Mapped, mapped_column, relationship

from app.core.enum              import ROLE_CODE_ENUM
from app.models.base_data_model import MEDICINE_MODEL, ROLE_MODEL
from app.models.base_model      import Base


class USER_MODEL(Base):
    """data.user — Staff / API user accounts for JWT authentication."""

    __tablename__  = "user"
    __table_args__ = {"schema": "data"}

    id                  : Mapped[uuid.UUID]          = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    username            : Mapped[str]                = mapped_column(String(100), nullable=False, unique=True)
    email               : Mapped[Optional[str]]      = mapped_column(String(255), nullable=True, unique=True)
    full_name           : Mapped[str]                = mapped_column(String(255), nullable=False)
    full_name_kh        : Mapped[Optional[str]]      = mapped_column(String(255), nullable=True)
    password_hash       : Mapped[str]                = mapped_column(Text, nullable=False)
    role_code           : Mapped[str]                = mapped_column(
        String(50)
        , ForeignKey("base_data.role.code")
        , nullable = False
        , default  = ROLE_CODE_ENUM.PHARMACIST.value
    )
    department_code     : Mapped[Optional[str]]      = mapped_column(
        String(50)
        , ForeignKey("base_data.department.code")
        , nullable = True
    )
    is_active           : Mapped[bool]               = mapped_column(Boolean, nullable=False, default=True)
    token_version       : Mapped[int]                = mapped_column(Integer, nullable=False, default=0)
    last_login_datetime : Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    role : Mapped[Optional["ROLE_MODEL"]] = relationship("ROLE_MODEL", foreign_keys=[role_code])


class REFRESH_TOKEN_MODEL(Base):
    """data.refresh_token — Tracks refresh token families for rotation, reuse detection & session listing."""

    __tablename__  = "refresh_token"
    __table_args__ = {"schema": "data"}

    id                 : Mapped[uuid.UUID]          = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id            : Mapped[uuid.UUID]          = mapped_column(
        UUID(as_uuid=True)
        , ForeignKey("data.user.id", ondelete="CASCADE")
        , nullable = False
    )
    family_id          : Mapped[uuid.UUID]          = mapped_column(UUID(as_uuid=True), nullable=False, default=uuid.uuid4)
    jti                : Mapped[str]                = mapped_column(String(100), nullable=False, unique=True)
    token_hash         : Mapped[Optional[str]]      = mapped_column(String(128), nullable=True, unique=True)
    replaced_by_jti    : Mapped[Optional[str]]      = mapped_column(String(100), nullable=True)
    device_id          : Mapped[Optional[str]]      = mapped_column(String(255), nullable=True)
    device_name        : Mapped[Optional[str]]      = mapped_column(String(255), nullable=True)
    platform           : Mapped[Optional[str]]      = mapped_column(String(50), nullable=True)
    ip_address         : Mapped[Optional[str]]      = mapped_column(String(100), nullable=True)
    user_agent         : Mapped[Optional[str]]      = mapped_column(Text, nullable=True)
    expires_at         : Mapped[datetime]           = mapped_column(DateTime, nullable=False)
    last_used_datetime : Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    revoked            : Mapped[bool]               = mapped_column(Boolean, nullable=False, default=False)
    revoked_datetime   : Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    revoke_reason      : Mapped[Optional[str]]      = mapped_column(String(100), nullable=True)


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
    date_out     : Mapped[Optional[date]] = mapped_column(Date, nullable=True)
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
    shift_code       : Mapped[Optional[str]]                     = mapped_column(String(20), nullable=True)
    payment_code     : Mapped[Optional[str]]                     = mapped_column(String(20), nullable=True)
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

    dispensing : Mapped["PATIENT_DISPENSING_MODEL"] = relationship(
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
    source          : Mapped[Optional[str]]  = mapped_column(String(255), nullable=True)
    total_qty       : Mapped[Decimal]        = mapped_column(Numeric(12, 2), nullable=False, default=0)
    remaining_qty   : Mapped[Decimal]        = mapped_column(Numeric(12, 2), nullable=False, default=0)
    input_date      : Mapped[date]           = mapped_column(Date, nullable=False, default=date.today)
    expire_date     : Mapped[Optional[date]] = mapped_column(Date, nullable=True, index=True)
    note            : Mapped[Optional[str]]  = mapped_column(Text, nullable=True)

    medicine : Mapped[Optional["MEDICINE_MODEL"]] = relationship("MEDICINE_MODEL", foreign_keys=[medicine_id])


class STOCK_MOVEMENT_MODEL(Base):
    """data.stock_movement — Audit ledger of stock IN, USAGE, EXPIRED, DAMAGED, and ADJUSTMENT movements."""

    __tablename__  = "stock_movement"
    __table_args__ = {"schema": "data"}

    id                 : Mapped[uuid.UUID]           = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    department_code    : Mapped[str]                 = mapped_column(
        String(50)
        , ForeignKey("base_data.department.code")
        , nullable = False
    )
    medicine_id        : Mapped[uuid.UUID]           = mapped_column(
        UUID(as_uuid=True)
        , ForeignKey("base_data.medicine.id")
        , nullable = False
    )
    batch_id           : Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True)
        , ForeignKey("data.stock_batch.id", ondelete="SET NULL")
        , nullable = True
    )
    dispensing_item_id : Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True)
        , ForeignKey("data.patient_dispensing_item.id", ondelete="SET NULL")
        , nullable = True
    )
    movement_type      : Mapped[str]                 = mapped_column(String(20), nullable=False)  # IN | USAGE | EXPIRED | DAMAGED | ADJUSTMENT
    movement_date      : Mapped[date]                = mapped_column(Date, nullable=False, default=date.today, index=True)
    quantity           : Mapped[Decimal]             = mapped_column(Numeric(12, 2), nullable=False, default=0)
    note               : Mapped[Optional[str]]       = mapped_column(Text, nullable=True)

    medicine        : Mapped[Optional["MEDICINE_MODEL"]]                = relationship("MEDICINE_MODEL", foreign_keys=[medicine_id])
    batch           : Mapped[Optional["STOCK_BATCH_MODEL"]]             = relationship("STOCK_BATCH_MODEL", foreign_keys=[batch_id])
    dispensing_item : Mapped[Optional["PATIENT_DISPENSING_ITEM_MODEL"]] = relationship("PATIENT_DISPENSING_ITEM_MODEL", foreign_keys=[dispensing_item_id])


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
        , ForeignKey("data.user.id", ondelete="SET NULL")
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
