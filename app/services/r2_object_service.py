import time
from typing import Any, Dict, Optional, Tuple

import boto3
from botocore.config     import Config
from botocore.exceptions import ClientError
from fastapi             import HTTPException, status

from app.core.config       import settings
from app.core.db           import getStaticSession
from app.core.enum         import AUTH_TYPE_ENUM, STATUS_CODE_ENUM, TRAFFIC_TYPE_ENUM
from app.core.log          import logger
from app.models.auth_model import CREDENTIAL_BASIC_MODEL, SYSTEM_CREDENTIAL_MODEL, SYSTEM_MODEL

R2_SYSTEM_CODE = "CLOUDFLARE_R2"
_CACHE_TTL     = 300  # seconds


class R2ObjectService:
    """Cloudflare R2 S3-compatible object storage service.

    Resolves outbound credentials from auth.system + auth.credential_basic (CLOUDFLARE_R2)
    with automatic fallback to .env settings.
    """

    _client            = None
    _cached_config     : Optional[Dict[str, Any]] = None
    _cache_expires_at  : float                    = 0.0


    @classmethod
    def _load_config_from_db(cls) -> Optional[Dict[str, Any]]:
        try:
            session = getStaticSession()
            try:
                system = (
                    session.query(SYSTEM_MODEL)
                    .filter(
                        SYSTEM_MODEL.code == R2_SYSTEM_CODE
                        , SYSTEM_MODEL.status_code == STATUS_CODE_ENUM.ACTIVE.value
                        , SYSTEM_MODEL.deleted_datetime.is_(None)
                    )
                    .first()
                )
                if not system:
                    return None

                cred = (
                    session.query(CREDENTIAL_BASIC_MODEL)
                    .join(
                        SYSTEM_CREDENTIAL_MODEL
                        , (SYSTEM_CREDENTIAL_MODEL.system_code == CREDENTIAL_BASIC_MODEL.system_code)
                        & (SYSTEM_CREDENTIAL_MODEL.traffic_type == TRAFFIC_TYPE_ENUM.OUTBOUND.value)
                        & (SYSTEM_CREDENTIAL_MODEL.auth_type_code == AUTH_TYPE_ENUM.BASIC.value)
                        & (SYSTEM_CREDENTIAL_MODEL.status_code == STATUS_CODE_ENUM.ACTIVE.value)
                        & (SYSTEM_CREDENTIAL_MODEL.deleted_datetime.is_(None))
                    )
                    .filter(
                        CREDENTIAL_BASIC_MODEL.system_code == R2_SYSTEM_CODE
                        , CREDENTIAL_BASIC_MODEL.traffic_type == TRAFFIC_TYPE_ENUM.OUTBOUND.value
                        , CREDENTIAL_BASIC_MODEL.status_code == STATUS_CODE_ENUM.ACTIVE.value
                        , CREDENTIAL_BASIC_MODEL.deleted_datetime.is_(None)
                    )
                    .first()
                )
                if not cred or not cred.username or not cred.password:
                    return None

                meta = system.metadata_json or {}
                endpoint_url = system.base_url or meta.get("endpoint_url") or ""
                if not endpoint_url and meta.get("account_id"):
                    endpoint_url = f"https://{meta['account_id']}.r2.cloudflarestorage.com"

                return {
                    "endpoint_url"               : endpoint_url
                    , "access_key_id"            : cred.username
                    , "secret_access_key"        : cred.password
                    , "bucket_name"              : meta.get("bucket_name") or settings.R2_BUCKET_NAME
                    , "region"                   : meta.get("region") or settings.R2_REGION or "auto"
                    , "presigned_expire_seconds" : int(meta.get("presigned_expire_seconds") or settings.R2_PRESIGNED_EXPIRE_SECONDS)
                }
            finally:
                session.close()
        except Exception as db_error:
            logger.warn(f"R2ObjectService._load_config_from_db: falling back to .env ({str(db_error)})")
            return None


    @classmethod
    def resolve_config(cls) -> Dict[str, Any]:
        """Return R2 config from auth.system (DB) or fall back to .env settings."""
        now = time.monotonic()
        if cls._cached_config is not None and now < cls._cache_expires_at:
            return cls._cached_config

        db_config = cls._load_config_from_db()
        if db_config and db_config.get("endpoint_url"):
            cls._cached_config    = db_config
            cls._cache_expires_at = now + _CACHE_TTL
            cls._client           = None
            return db_config

        endpoint_url = settings.R2_ENDPOINT_URL
        if not endpoint_url and settings.R2_ACCOUNT_ID:
            endpoint_url = f"https://{settings.R2_ACCOUNT_ID}.r2.cloudflarestorage.com"

        env_config = {
            "endpoint_url"               : endpoint_url
            , "access_key_id"            : settings.R2_ACCESS_KEY_ID
            , "secret_access_key"        : settings.R2_SECRET_ACCESS_KEY
            , "bucket_name"              : settings.R2_BUCKET_NAME
            , "region"                   : settings.R2_REGION or "auto"
            , "presigned_expire_seconds" : settings.R2_PRESIGNED_EXPIRE_SECONDS
        }
        cls._cached_config    = env_config
        cls._cache_expires_at = now + _CACHE_TTL
        return env_config


    @classmethod
    def _get_client(cls) -> Tuple[Any, Dict[str, Any]]:
        cfg = cls.resolve_config()
        if cls._client is not None:
            return cls._client, cfg

        if not cfg["endpoint_url"] or not cfg["access_key_id"] or not cfg["secret_access_key"]:
            logger.error("R2ObjectService._get_client: Cloudflare R2 credentials are not configured.")
            raise HTTPException(
                status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
                , detail    = "Cloudflare R2 credentials are not configured."
            )

        cls._client = boto3.client(
            "s3"
            , endpoint_url          = cfg["endpoint_url"]
            , aws_access_key_id     = cfg["access_key_id"]
            , aws_secret_access_key = cfg["secret_access_key"]
            , region_name           = cfg["region"]
            , config                = Config(signature_version = "s3v4")
        )
        return cls._client, cfg


    @classmethod
    def upload_bytes(
        cls
        , object_key   : str
        , data         : bytes
        , content_type : str = "application/octet-stream"
        , bucket       : Optional[str] = None
    ) -> str:
        client, cfg = cls._get_client()
        bucket_name = bucket or cfg["bucket_name"]
        try:
            client.put_object(
                Bucket        = bucket_name
                , Key         = object_key
                , Body        = data
                , ContentType = content_type
            )
            logger.info(
                "R2ObjectService.upload_bytes: uploaded"
                , f"bucket: {bucket_name}"
                , f"key: {object_key}"
                , f"size: {len(data)}"
            )
            return object_key
        except ClientError as exc:
            logger.error(
                "R2ObjectService.upload_bytes: upload failed"
                , f"bucket: {bucket_name}"
                , f"key: {object_key}"
                , f"error: {exc}"
            )
            raise HTTPException(
                status_code = status.HTTP_502_BAD_GATEWAY
                , detail    = f"Failed to upload object to R2: {exc}"
            )


    @classmethod
    def get_object_bytes(
        cls
        , object_key : str
        , bucket     : Optional[str] = None
    ) -> bytes:
        client, cfg = cls._get_client()
        bucket_name = bucket or cfg["bucket_name"]
        try:
            resp = client.get_object(Bucket = bucket_name, Key = object_key)
            return resp["Body"].read()
        except ClientError as exc:
            code = exc.response.get("Error", {}).get("Code", "")
            if code in ("NoSuchKey", "404"):
                logger.warn(
                    "R2ObjectService.get_object_bytes: object not found"
                    , f"bucket: {bucket_name}"
                    , f"key: {object_key}"
                )
                raise HTTPException(
                    status_code = status.HTTP_404_NOT_FOUND
                    , detail    = "File not found in R2 storage."
                )
            logger.error(
                "R2ObjectService.get_object_bytes: read failed"
                , f"bucket: {bucket_name}"
                , f"key: {object_key}"
                , f"error: {exc}"
            )
            raise HTTPException(
                status_code = status.HTTP_502_BAD_GATEWAY
                , detail    = f"Failed to read object from R2: {exc}"
            )


    @classmethod
    def delete_object(
        cls
        , object_key : str
        , bucket     : Optional[str] = None
    ) -> None:
        client, cfg = cls._get_client()
        bucket_name = bucket or cfg["bucket_name"]
        try:
            client.delete_object(Bucket = bucket_name, Key = object_key)
            logger.info(
                "R2ObjectService.delete_object: deleted"
                , f"bucket: {bucket_name}"
                , f"key: {object_key}"
            )
        except ClientError as exc:
            logger.error(
                "R2ObjectService.delete_object: delete failed"
                , f"bucket: {bucket_name}"
                , f"key: {object_key}"
                , f"error: {exc}"
            )
            raise HTTPException(
                status_code = status.HTTP_502_BAD_GATEWAY
                , detail    = f"Failed to delete object from R2: {exc}"
            )


    @classmethod
    def generate_presigned_url(
        cls
        , object_key  : str
        , expires_in  : Optional[int] = None
        , bucket      : Optional[str] = None
        , disposition : str = "inline"
        , filename    : Optional[str] = None
    ) -> str:
        client, cfg = cls._get_client()
        bucket_name = bucket or cfg["bucket_name"]
        params      = {
            "Bucket" : bucket_name
            , "Key"  : object_key
        }
        if filename:
            params["ResponseContentDisposition"] = f'{disposition}; filename="{filename}"'
        try:
            return client.generate_presigned_url(
                ClientMethod = "get_object"
                , Params     = params
                , ExpiresIn  = expires_in or cfg["presigned_expire_seconds"]
            )
        except ClientError as exc:
            logger.error(
                "R2ObjectService.generate_presigned_url: failed"
                , f"bucket: {bucket_name}"
                , f"key: {object_key}"
                , f"error: {exc}"
            )
            raise HTTPException(
                status_code = status.HTTP_502_BAD_GATEWAY
                , detail    = f"Failed to generate presigned URL: {exc}"
            )
