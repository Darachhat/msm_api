import secrets
import urllib.parse
from datetime import datetime
from typing   import Optional

from fastapi          import HTTPException, status
from fastapi.responses import Response
from sqlalchemy.orm   import Session

from app.core.config        import settings
from app.core.enum          import STATUS_CODE_ENUM
from app.models.data_model  import FILE_OBJECT_MODEL
from app.services.r2_object_service import R2ObjectService


class FileService:
    """OSM-compatible file registry and preview/download URL service backed by Cloudflare R2."""

    @staticmethod
    def _generate_path_code() -> str:
        return secrets.token_urlsafe(12)


    @classmethod
    def upload_and_register(
        cls
        , session    : Session
        , content    : bytes
        , filename   : str
        , ext        : str
        , mime_type  : str
        , title      : Optional[str] = None
        , module     : str = "reports"
        , created_by : Optional[str] = None
    ) -> FILE_OBJECT_MODEL:
        clean_ext   = ext if ext.startswith(".") else f".{ext}"
        path_code   = cls._generate_path_code()
        date_prefix = datetime.utcnow().strftime("%Y/%m/%d")
        object_key  = f"{module}/{date_prefix}/{path_code}{clean_ext}"

        R2ObjectService.upload_bytes(
            object_key     = object_key
            , data         = content
            , content_type = mime_type
        )

        base         = settings.APP_BASE_URL.rstrip("/")
        api_prefix   = settings.API_V1_STR.rstrip("/")
        preview_url  = f"{base}{api_prefix}/files/preview/{path_code}"
        download_url = f"{base}{api_prefix}/files/download/{path_code}"

        file_obj = FILE_OBJECT_MODEL(
            path_code        = path_code
            , title          = title or filename
            , filename       = filename
            , ext            = clean_ext
            , mime_type      = mime_type
            , size           = len(content)
            , r2_bucket      = settings.R2_BUCKET_NAME
            , r2_object_key  = object_key
            , module         = module
            , preview_url    = preview_url
            , download_url   = download_url
            , accessed_count = 0
            , status_code    = STATUS_CODE_ENUM.ACTIVE.value
            , created_by     = created_by
        )
        session.add(file_obj)
        session.flush()
        return file_obj


    @classmethod
    def get_by_path_code(cls, session: Session, path_code: str) -> FILE_OBJECT_MODEL:
        file_obj = (
            session.query(FILE_OBJECT_MODEL)
            .filter(
                FILE_OBJECT_MODEL.path_code == path_code
                , FILE_OBJECT_MODEL.status_code == STATUS_CODE_ENUM.ACTIVE.value
                , FILE_OBJECT_MODEL.deleted_datetime.is_(None)
            )
            .first()
        )
        if not file_obj:
            raise HTTPException(
                status_code = status.HTTP_404_NOT_FOUND
                , detail    = "File not found."
            )
        return file_obj


    @classmethod
    def serve_file(
        cls
        , session   : Session
        , path_code : str
        , inline    : bool = False
    ) -> Response:
        file_obj = cls.get_by_path_code(session, path_code)
        file_obj.accessed_count = (file_obj.accessed_count or 0) + 1
        session.commit()

        data = R2ObjectService.get_object_bytes(
            object_key = file_obj.r2_object_key
            , bucket   = file_obj.r2_bucket
        )
        full_name = (
            file_obj.filename
            if file_obj.filename.endswith(file_obj.ext)
            else f"{file_obj.filename}{file_obj.ext}"
        )
        encoded_name = urllib.parse.quote(full_name)
        disposition  = "inline" if inline else "attachment"

        return Response(
            content    = data
            , media_type = file_obj.mime_type
            , headers  = {
                "Content-Disposition": f"{disposition}; filename*=UTF-8''{encoded_name}"
                , "Content-Length"   : str(len(data))
            }
        )


    @classmethod
    def get_presigned_url(
        cls
        , session   : Session
        , path_code : str
        , inline    : bool = False
    ) -> dict:
        file_obj = cls.get_by_path_code(session, path_code)
        full_name = (
            file_obj.filename
            if file_obj.filename.endswith(file_obj.ext)
            else f"{file_obj.filename}{file_obj.ext}"
        )
        url = R2ObjectService.generate_presigned_url(
            object_key    = file_obj.r2_object_key
            , bucket      = file_obj.r2_bucket
            , disposition = "inline" if inline else "attachment"
            , filename    = full_name
        )
        return {
            "path_code"    : file_obj.path_code
            , "filename"   : full_name
            , "url"        : url
            , "expires_in" : settings.R2_PRESIGNED_EXPIRE_SECONDS
        }
