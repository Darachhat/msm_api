from typing import List, Optional

from fastapi        import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile, status
from sqlalchemy.orm import Session

from app.api.deps.auth_deps         import require_permission
from app.core.config                import settings
from app.core.constants             import ALLOWED_SIGNATURE_EXTS, ALLOWED_SIGNATURE_MIMES
from app.core.db                    import getSession
from app.core.enum                  import PERMISSION_ACTION_ENUM, SERVICE_MODULE_ENUM
from app.models.data_model          import USER_MODEL
from app.schemas.base_schema        import IResponseBase
from app.schemas.signature_schema   import SignatureCreate, SignatureResponse
from app.services.signature_service import SignatureService

router = APIRouter()


@router.post(
    ""
    , response_model = IResponseBase[SignatureResponse]
    , summary        = "Save digital signature (base64 JSON)"
)
def save_signature_json(
    payload        : SignatureCreate
    , session      : Session    = Depends(getSession)
    , current_user : USER_MODEL = Depends(
        require_permission(SERVICE_MODULE_ENUM.DISPENSING.value, PERMISSION_ACTION_ENUM.WRITE)
    )
):
    res = SignatureService.save_signature(
        session    = session
        , payload  = payload
        , user_id  = current_user.id
        , username = current_user.username
    )
    return IResponseBase(
        data      = res
        , message = "Signature saved"
    )


@router.post(
    "/upload"
    , response_model = IResponseBase[SignatureResponse]
    , summary        = "Upload digital signature image to R2"
)
async def upload_signature_image(
    signer_name    : str           = Form(...)
    , signer_role  : Optional[str] = Form(None)
    , is_default   : bool          = Form(False)
    , file         : UploadFile    = File(...)
    , session      : Session       = Depends(getSession)
    , current_user : USER_MODEL    = Depends(
        require_permission(SERVICE_MODULE_ENUM.DISPENSING.value, PERMISSION_ACTION_ENUM.WRITE)
    )
):
    mime_type = (file.content_type or "").lower()
    if mime_type not in ALLOWED_SIGNATURE_MIMES:
        raise HTTPException(
            status_code = status.HTTP_400_BAD_REQUEST
            , detail    = f"Unsupported signature image type '{mime_type}'. Allowed: PNG, JPEG, WEBP."
        )

    ext = ("." + file.filename.rsplit(".", 1)[-1].lower()) if (file.filename and "." in file.filename) else ".png"
    if ext not in ALLOWED_SIGNATURE_EXTS:
        raise HTTPException(
            status_code = status.HTTP_400_BAD_REQUEST
            , detail    = f"Unsupported file extension '{ext}'."
        )

    content = await file.read(settings.MAX_SIGNATURE_UPLOAD_BYTES + 1)
    if not content:
        raise HTTPException(
            status_code = status.HTTP_400_BAD_REQUEST
            , detail    = "Uploaded signature image is empty."
        )
    if len(content) > settings.MAX_SIGNATURE_UPLOAD_BYTES:
        raise HTTPException(
            status_code = status.HTTP_413_REQUEST_ENTITY_TOO_LARGE
            , detail    = f"Signature image exceeds maximum size of {settings.MAX_SIGNATURE_UPLOAD_BYTES // (1024 * 1024)} MB."
        )

    res = SignatureService.save_signature(
        session       = session
        , payload     = SignatureCreate(
            signer_name   = signer_name
            , signer_role = signer_role
            , is_default  = is_default
        )
        , user_id     = current_user.id
        , username    = current_user.username
        , image_bytes = content
        , image_ext   = ext
        , image_mime  = mime_type
    )
    return IResponseBase(
        data      = res
        , message = "Signature image uploaded"
    )


@router.get(
    ""
    , response_model = IResponseBase[List[SignatureResponse]]
    , summary        = "List previous digital signatures"
)
def list_signatures(
    mine_only      : bool          = Query(False)
    , signer_role  : Optional[str] = Query(None)
    , signer_name  : Optional[str] = Query(None)
    , limit        : int           = Query(100, ge = 1, le = 500)
    , offset       : int           = Query(0, ge = 0)
    , session      : Session       = Depends(getSession)
    , current_user : USER_MODEL    = Depends(
        require_permission(SERVICE_MODULE_ENUM.DISPENSING.value, PERMISSION_ACTION_ENUM.READ)
    )
):
    res = SignatureService.list_previous_signatures(
        session       = session
        , user_id     = current_user.id if mine_only else None
        , signer_role = signer_role
        , signer_name = signer_name
        , limit       = limit
        , offset      = offset
    )
    return IResponseBase(data = res)
