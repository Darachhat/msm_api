from typing import List, Optional

from fastapi        import APIRouter, Depends, File, Form, Query, UploadFile
from sqlalchemy.orm import Session

from app.api.deps.auth_deps         import get_current_user
from app.core.db                    import getSession
from app.models.auth_model          import USER_MODEL
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
    , session      : Session = Depends(getSession)
    , current_user : USER_MODEL = Depends(get_current_user)
):
    res = SignatureService.save_signature(
        session      = session
        , payload    = payload
        , user_id    = current_user.id
        , username   = current_user.username
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
    signer_name    : str = Form(...)
    , signer_role  : Optional[str] = Form(None)
    , is_default   : bool = Form(False)
    , file         : UploadFile = File(...)
    , session      : Session = Depends(getSession)
    , current_user : USER_MODEL = Depends(get_current_user)
):
    content = await file.read()
    ext     = "." + file.filename.split(".")[-1] if file.filename and "." in file.filename else ".png"
    res     = SignatureService.save_signature(
        session        = session
        , payload      = SignatureCreate(
            signer_name   = signer_name
            , signer_role = signer_role
            , is_default  = is_default
        )
        , user_id      = current_user.id
        , username     = current_user.username
        , image_bytes  = content
        , image_ext    = ext
        , image_mime   = file.content_type or "image/png"
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
    mine_only      : bool = Query(False)
    , signer_role  : Optional[str] = Query(None)
    , signer_name  : Optional[str] = Query(None)
    , session      : Session = Depends(getSession)
    , current_user : USER_MODEL = Depends(get_current_user)
):
    res = SignatureService.list_previous_signatures(
        session        = session
        , user_id      = current_user.id if mine_only else None
        , signer_role  = signer_role
        , signer_name  = signer_name
    )
    return IResponseBase(data = res)
