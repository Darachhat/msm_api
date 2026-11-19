from typing import List, Optional
from uuid   import UUID
from sqlalchemy.orm import Session, joinedload

from app.core.enum              import STATUS_CODE_ENUM
from app.models.data_model      import DIGITAL_SIGNATURE_MODEL
from app.schemas.signature_schema import SignatureCreate, SignatureResponse
from app.services.file_service  import FileService


class SignatureService:
    """Stores and retrieves digital signatures for Doctors, Nurses, and Pharmacists."""

    @staticmethod
    def _to_response(sig: DIGITAL_SIGNATURE_MODEL) -> SignatureResponse:
        return SignatureResponse(
            id                 = sig.id
            , user_id          = sig.user_id
            , signer_name      = sig.signer_name
            , signer_role      = sig.signer_role
            , signature_data   = sig.signature_data
            , preview_url      = sig.file_object.preview_url if sig.file_object else None
            , is_default       = sig.is_default
            , created_datetime = sig.created_datetime
        )


    @classmethod
    def save_signature(
        cls
        , session     : Session
        , payload     : SignatureCreate
        , user_id     : UUID
        , username    : str
        , image_bytes : Optional[bytes] = None
        , image_ext   : Optional[str] = None
        , image_mime  : Optional[str] = None
    ) -> SignatureResponse:
        file_obj = None
        if image_bytes and image_ext and image_mime:
            file_obj = FileService.upload_and_register(
                session      = session
                , content    = image_bytes
                , filename   = f"sig_{payload.signer_name}"
                , ext        = image_ext
                , mime_type  = image_mime
                , title      = f"Signature - {payload.signer_name}"
                , module     = "signatures"
                , created_by = username
            )

        if payload.is_default:
            session.query(DIGITAL_SIGNATURE_MODEL).filter(
                DIGITAL_SIGNATURE_MODEL.user_id == user_id
                , DIGITAL_SIGNATURE_MODEL.is_default.is_(True)
            ).update({"is_default": False})

        sig = DIGITAL_SIGNATURE_MODEL(
            user_id          = user_id
            , signer_name    = payload.signer_name
            , signer_role    = payload.signer_role
            , file_object_id = file_obj.id if file_obj else None
            , signature_data = payload.signature_data
            , is_default     = payload.is_default
            , created_by     = username
        )
        session.add(sig)
        session.commit()
        session.refresh(sig)
        sig.file_object = file_obj
        return cls._to_response(sig)


    @classmethod
    def list_previous_signatures(
        cls
        , session      : Session
        , user_id      : Optional[UUID] = None
        , signer_role  : Optional[str] = None
        , signer_name  : Optional[str] = None
    ) -> List[SignatureResponse]:
        query = (
            session.query(DIGITAL_SIGNATURE_MODEL)
            .options(joinedload(DIGITAL_SIGNATURE_MODEL.file_object))
            .filter(
                DIGITAL_SIGNATURE_MODEL.status_code == STATUS_CODE_ENUM.ACTIVE.value
                , DIGITAL_SIGNATURE_MODEL.deleted_datetime.is_(None)
            )
        )
        if user_id:
            query = query.filter(DIGITAL_SIGNATURE_MODEL.user_id == user_id)
        if signer_role:
            query = query.filter(DIGITAL_SIGNATURE_MODEL.signer_role == signer_role)
        if signer_name:
            query = query.filter(DIGITAL_SIGNATURE_MODEL.signer_name.ilike(f"%{signer_name}%"))

        rows = query.order_by(
            DIGITAL_SIGNATURE_MODEL.is_default.desc()
            , DIGITAL_SIGNATURE_MODEL.created_datetime.desc()
        ).all()
        return [cls._to_response(r) for r in rows]
