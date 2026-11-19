from fastapi        import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.deps.auth_deps    import get_current_user
from app.core.db               import getSession
from app.models.auth_model     import USER_MODEL
from app.schemas.base_schema   import IResponseBase
from app.schemas.report_schema import FileObjectResponse
from app.services.file_service import FileService

router = APIRouter()


@router.get(
    "/preview/{path_code}"
    , summary = "Preview file inline via path_code (OSM-style)"
)
def preview_file(
    path_code : str
    , session : Session = Depends(getSession)
):
    return FileService.serve_file(
        session     = session
        , path_code = path_code
        , inline    = True
    )


@router.get(
    "/download/{path_code}"
    , summary = "Download file as attachment via path_code (OSM-style)"
)
def download_file(
    path_code : str
    , session : Session = Depends(getSession)
):
    return FileService.serve_file(
        session     = session
        , path_code = path_code
        , inline    = False
    )


@router.get(
    "/presigned/{path_code}"
    , response_model = IResponseBase[dict]
    , summary        = "Get temporary Cloudflare R2 presigned URL for preview or download"
)
def get_presigned_url(
    path_code      : str
    , inline       : bool = Query(False)
    , session      : Session = Depends(getSession)
    , current_user : USER_MODEL = Depends(get_current_user)
):
    data = FileService.get_presigned_url(
        session     = session
        , path_code = path_code
        , inline    = inline
    )
    return IResponseBase(data = data)


@router.get(
    "/meta/{path_code}"
    , response_model = IResponseBase[FileObjectResponse]
    , summary        = "Get file metadata by path_code"
)
def get_file_meta(
    path_code      : str
    , session      : Session = Depends(getSession)
    , current_user : USER_MODEL = Depends(get_current_user)
):
    file_obj = FileService.get_by_path_code(
        session     = session
        , path_code = path_code
    )
    return IResponseBase(data = FileObjectResponse.model_validate(file_obj))
