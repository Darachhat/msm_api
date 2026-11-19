from typing import Optional
import uuid

from sqlalchemy                     import Boolean, ForeignKey, Integer, SmallInteger, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm                 import Mapped, mapped_column, relationship

from app.models.base_model import Base


class TRANSLATE_MODEL(Base):
    __tablename__  = "translate"
    __table_args__ = {"schema": "base_data"}

    id          : Mapped[uuid.UUID]     = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    ref_id      : Mapped[uuid.UUID]     = mapped_column(UUID(as_uuid=True), nullable=False)
    schema_name : Mapped[str]           = mapped_column(String(100), nullable=False)
    table_name  : Mapped[str]           = mapped_column(String(100), nullable=False)
    column_name : Mapped[str]           = mapped_column(String(100), nullable=False)
    en          : Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    km          : Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    cn          : Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    jp          : Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    kr          : Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    note        : Mapped[Optional[str]] = mapped_column(Text, nullable=True)


class STATUS_MODEL(Base):
    __tablename__  = "status"
    __table_args__ = {"schema": "base_data"}

    id           : Mapped[uuid.UUID]           = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    code         : Mapped[str]                 = mapped_column(String(100), nullable=False, unique=True)
    name         : Mapped[str]                 = mapped_column(String(255), nullable=False)
    translate_id : Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True)
        , ForeignKey("base_data.translate.id")
        , nullable = True
    )

    translate : Mapped[Optional["TRANSLATE_MODEL"]] = relationship("TRANSLATE_MODEL", foreign_keys=[translate_id])


class DEPARTMENT_MODEL(Base):
    """base_data.department — Hospital department (e.g., SURGICAL_ICU)."""

    __tablename__  = "department"
    __table_args__ = {"schema": "base_data"}

    id               : Mapped[uuid.UUID]           = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    code             : Mapped[str]                 = mapped_column(String(50), nullable=False, unique=True)
    name             : Mapped[str]                 = mapped_column(String(255), nullable=False)
    name_kh          : Mapped[str]                 = mapped_column(String(255), nullable=False)
    hospital_name    : Mapped[Optional[str]]       = mapped_column(String(255), nullable=True)
    hospital_name_kh : Mapped[Optional[str]]       = mapped_column(String(255), nullable=True)
    doc_number       : Mapped[Optional[str]]       = mapped_column(String(50), nullable=True)
    translate_id     : Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True)
        , ForeignKey("base_data.translate.id")
        , nullable = True
    )

    translate : Mapped[Optional["TRANSLATE_MODEL"]] = relationship("TRANSLATE_MODEL", foreign_keys=[translate_id])


class MEDICINE_CATEGORY_MODEL(Base):
    """base_data.medicine_category — TABLET (ថ្នាំគ្រាប់) / INJECTION (ថ្នាំចាក់)."""

    __tablename__  = "medicine_category"
    __table_args__ = {"schema": "base_data"}

    id           : Mapped[uuid.UUID]           = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    code         : Mapped[str]                 = mapped_column(String(50), nullable=False, unique=True)
    name         : Mapped[str]                 = mapped_column(String(150), nullable=False)
    name_kh      : Mapped[str]                 = mapped_column(String(150), nullable=False)
    record_order : Mapped[int]                 = mapped_column(SmallInteger, nullable=False, default=0)
    translate_id : Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True)
        , ForeignKey("base_data.translate.id")
        , nullable = True
    )


class MEDICINE_FORM_MODEL(Base):
    """base_data.medicine_form — គ្រាប់ / Amp / FL / Solution / Gel / Aerosol."""

    __tablename__  = "medicine_form"
    __table_args__ = {"schema": "base_data"}

    id           : Mapped[uuid.UUID]     = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    code         : Mapped[str]           = mapped_column(String(50), nullable=False, unique=True)
    name         : Mapped[str]           = mapped_column(String(100), nullable=False)
    name_kh      : Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    unit_label   : Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    record_order : Mapped[int]           = mapped_column(SmallInteger, nullable=False, default=0)


class MEDICINE_MODEL(Base):
    """base_data.medicine — Master medicine catalog (146+ items across tablets, injections, narcotics)."""

    __tablename__  = "medicine"
    __table_args__ = {"schema": "base_data"}

    id              : Mapped[uuid.UUID]           = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    code            : Mapped[str]                 = mapped_column(String(100), nullable=False, unique=True)
    name            : Mapped[str]                 = mapped_column(String(255), nullable=False)
    category_code   : Mapped[str]                 = mapped_column(
        String(50)
        , ForeignKey("base_data.medicine_category.code")
        , nullable = False
    )
    form_code       : Mapped[str]                 = mapped_column(
        String(50)
        , ForeignKey("base_data.medicine_form.code")
        , nullable = False
    )
    dosage          : Mapped[Optional[str]]       = mapped_column(String(100), nullable=True)
    unit_label      : Mapped[Optional[str]]       = mapped_column(String(50), nullable=True)
    is_narcotic     : Mapped[bool]                = mapped_column(Boolean, nullable=False, default=False)
    narcotic_doc_no : Mapped[Optional[str]]       = mapped_column(String(50), nullable=True)
    sort_order      : Mapped[int]                 = mapped_column(Integer, nullable=False, default=0)
    translate_id    : Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True)
        , ForeignKey("base_data.translate.id")
        , nullable = True
    )

    category : Mapped[Optional["MEDICINE_CATEGORY_MODEL"]] = relationship(
        "MEDICINE_CATEGORY_MODEL"
        , foreign_keys = [category_code]
    )
    form     : Mapped[Optional["MEDICINE_FORM_MODEL"]]     = relationship(
        "MEDICINE_FORM_MODEL"
        , foreign_keys = [form_code]
    )


class REPORT_TYPE_MODEL(Base):
    """base_data.report_type — Supported Excel report templates."""

    __tablename__  = "report_type"
    __table_args__ = {"schema": "base_data"}

    id          : Mapped[uuid.UUID]     = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    code        : Mapped[str]           = mapped_column(String(50), nullable=False, unique=True)
    name        : Mapped[str]           = mapped_column(String(255), nullable=False)
    name_kh     : Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    description : Mapped[Optional[str]] = mapped_column(Text, nullable=True)
