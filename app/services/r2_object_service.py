from typing import Optional

import boto3
from botocore.config     import Config
from botocore.exceptions import ClientError
from fastapi             import HTTPException, status

from app.core.config import settings


class R2ObjectService:
    """Cloudflare R2 S3-compatible object storage service."""

    _client = None


    @classmethod
    def _get_client(cls):
        if cls._client is not None:
            return cls._client

        endpoint_url = settings.R2_ENDPOINT_URL
        if not endpoint_url and settings.R2_ACCOUNT_ID:
            endpoint_url = f"https://{settings.R2_ACCOUNT_ID}.r2.cloudflarestorage.com"

        if not endpoint_url or not settings.R2_ACCESS_KEY_ID or not settings.R2_SECRET_ACCESS_KEY:
            raise HTTPException(
                status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
                , detail    = "Cloudflare R2 credentials are not configured."
            )

        cls._client = boto3.client(
            "s3"
            , endpoint_url          = endpoint_url
            , aws_access_key_id     = settings.R2_ACCESS_KEY_ID
            , aws_secret_access_key = settings.R2_SECRET_ACCESS_KEY
            , region_name           = settings.R2_REGION or "auto"
            , config                = Config(signature_version = "s3v4")
        )
        return cls._client


    @classmethod
    def upload_bytes(
        cls
        , object_key   : str
        , data         : bytes
        , content_type : str = "application/octet-stream"
        , bucket       : Optional[str] = None
    ) -> str:
        bucket_name = bucket or settings.R2_BUCKET_NAME
        client      = cls._get_client()
        try:
            client.put_object(
                Bucket       = bucket_name
                , Key        = object_key
                , Body       = data
                , ContentType= content_type
            )
            return object_key
        except ClientError as exc:
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
        bucket_name = bucket or settings.R2_BUCKET_NAME
        client      = cls._get_client()
        try:
            resp = client.get_object(Bucket = bucket_name, Key = object_key)
            return resp["Body"].read()
        except ClientError as exc:
            code = exc.response.get("Error", {}).get("Code", "")
            if code in ("NoSuchKey", "404"):
                raise HTTPException(
                    status_code = status.HTTP_404_NOT_FOUND
                    , detail    = "File not found in R2 storage."
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
        bucket_name = bucket or settings.R2_BUCKET_NAME
        client      = cls._get_client()
        try:
            client.delete_object(Bucket = bucket_name, Key = object_key)
        except ClientError as exc:
            raise HTTPException(
                status_code = status.HTTP_502_BAD_GATEWAY
                , detail    = f"Failed to delete object from R2: {exc}"
            )


    @classmethod
    def generate_presigned_url(
        cls
        , object_key    : str
        , expires_in    : Optional[int] = None
        , bucket        : Optional[str] = None
        , disposition   : str = "inline"
        , filename      : Optional[str] = None
    ) -> str:
        bucket_name = bucket or settings.R2_BUCKET_NAME
        client      = cls._get_client()
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
                , ExpiresIn  = expires_in or settings.R2_PRESIGNED_EXPIRE_SECONDS
            )
        except ClientError as exc:
            raise HTTPException(
                status_code = status.HTTP_502_BAD_GATEWAY
                , detail    = f"Failed to generate presigned URL: {exc}"
            )
