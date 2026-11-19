import json
import traceback
from datetime import datetime, timezone
from time     import perf_counter
from typing   import Any, Optional, Tuple

from fastapi                    import Request, Response, status
from fastapi.exception_handlers import request_validation_exception_handler
from fastapi.exceptions         import RequestValidationError
from fastapi.responses          import JSONResponse
from starlette.concurrency      import iterate_in_threadpool
from starlette.exceptions       import HTTPException

from app.core.constants         import CONTENT_TYPE_JSON
from app.core.enum              import CHANNEL_ENUM, STATUS_CODE_ENUM, TRAFFIC_TYPE_ENUM
from app.core.log               import logger
from app.core.system_log_utils  import SystemLogUtils
from app.schemas.base_schema    import get_ulid
from app.schemas.system_log_schema import SYSTEM_LOG_DATA


def _parse_content_type(header_content_type: Optional[str]) -> Optional[str]:
    if not header_content_type:
        return None
    lower_ct = header_content_type.lower()
    if lower_ct.startswith('multipart/form-data'):
        return 'multipart/form-data'
    if lower_ct.startswith('application/x-www-form-urlencoded'):
        return 'application/x-www-form-urlencoded'
    if lower_ct.startswith(CONTENT_TYPE_JSON):
        return CONTENT_TYPE_JSON
    return header_content_type.split(';', 1)[0].strip()


async def _extract_request_body(request: Request, content_type: Optional[str]) -> Optional[Any]:
    if request.method not in ('PUT', 'POST', 'PATCH'):
        return None
    if not content_type:
        return None

    try:
        body_bytes = await request.body()
        if not body_bytes:
            return None
        if content_type == 'multipart/form-data':
            return {'raw': f'<multipart/form-data, length: {len(body_bytes)}>'}
        try:
            return body_bytes.decode('utf-8')
        except UnicodeDecodeError:
            return {'raw': f'<binary data, length: {len(body_bytes)}>'}
    except Exception as extract_error:
        logger.error(f'LogMiddleware._extract_request_body Exception: {str(extract_error)}')
        return None


async def _extract_response_body(response: Response) -> Tuple[bytes, Response]:
    """Read response body bytes safely while preserving the response stream for the client."""
    if not hasattr(response, 'body_iterator'):
        return getattr(response, 'body', b'') or b'', response

    chunks = [chunk async for chunk in response.body_iterator]
    response.body_iterator = iterate_in_threadpool(iter(chunks))
    return b''.join(chunks), response


def _parse_response_body(response_bytes: bytes, content_type: Optional[str]) -> Optional[Any]:
    if not response_bytes:
        return None
    lower_ct = (content_type or '').lower()
    if any(
        binary_hint in lower_ct
        for binary_hint in ('application/octet-stream', 'spreadsheetml', 'application/pdf', 'image/')
    ):
        return {'raw': f'<binary response ({content_type}), length: {len(response_bytes)}>'}
    try:
        decoded = response_bytes.decode('utf-8')
        return SystemLogUtils.parse_body(decoded)
    except UnicodeDecodeError:
        return {'raw': f'<binary response, length: {len(response_bytes)}>'}


def _extract_trace_id(parsed_response_body: Any) -> str:
    if isinstance(parsed_response_body, dict):
        trace_id = parsed_response_body.get('trace_id')
        if trace_id and str(trace_id).strip():
            return str(trace_id).strip()
    return get_ulid()


class LogMiddleware:

    @staticmethod
    async def log_access(request: Request, call_next) -> Response:
        """Log every inbound HTTP request to logs/app.log and asynchronously to track.system_log."""
        start_time   = perf_counter()
        req_datetime = datetime.now(timezone.utc)

        header_content_type = request.headers.get('content-type') or ''
        content_type        = _parse_content_type(header_content_type)
        raw_request_body    = await _extract_request_body(request, content_type)
        parsed_request_body = SystemLogUtils.parse_body(raw_request_body)

        if request.query_params:
            query_dict = dict(request.query_params)
            if parsed_request_body is None:
                parsed_request_body = query_dict
            elif isinstance(parsed_request_body, dict):
                parsed_request_body = {**query_dict, **parsed_request_body}

        client_ip = request.client.host if request.client else None

        response                      = await call_next(request)
        response_bytes, response      = await _extract_response_body(response)
        res_datetime                  = datetime.now(timezone.utc)
        duration_seconds              = round(perf_counter() - start_time, 4)
        duration_ms                   = round(duration_seconds * 1000, 2)

        response_content_type = response.headers.get('content-type')
        parsed_response_body  = _parse_response_body(response_bytes, response_content_type)
        trace_id              = _extract_trace_id(parsed_response_body)

        # File log (logs/app.log)
        access_message = (
            f'{request.method} {request.url.path} {response.status_code} '
            f'{duration_ms}ms ip: {client_ip or "N/A"}'
        )
        if response.status_code >= status.HTTP_500_INTERNAL_SERVER_ERROR:
            logger.error(access_message)
        elif response.status_code >= status.HTTP_400_BAD_REQUEST:
            logger.warn(access_message)
        else:
            logger.info(access_message)

        # Database audit log (track.system_log) — non-blocking background write
        system_log_data = SYSTEM_LOG_DATA(
            traffic_type           = TRAFFIC_TYPE_ENUM.INBOUND.value
            , system_code          = getattr(request.state, 'system_code', None) or 'MSM_API'
            , channel              = getattr(request.state, 'channel', None) or CHANNEL_ENUM.API.value
            , request_method       = request.method
            , request_endpoint     = str(request.url.path)
            , request_netloc       = f'{request.url.scheme}://{request.url.netloc}' if request.url.netloc else None
            , request_content_type = content_type
            , request_user_agent   = request.headers.get('user-agent')
            , request_headers      = SystemLogUtils.sanitize_headers(dict(request.headers))
            , request_body         = parsed_request_body
            , requested_datetime   = req_datetime.replace(tzinfo=None)
            , client_ip            = client_ip
            , response_code        = response.status_code
            , response_headers     = SystemLogUtils.sanitize_headers(dict(response.headers))
            , response_body        = parsed_response_body
            , response_duration    = duration_seconds
            , response_datetime    = res_datetime.replace(tzinfo=None)
            , client_log_id        = trace_id
            , status_code          = STATUS_CODE_ENUM.ACTIVE.value
            , created_datetime     = res_datetime.replace(tzinfo=None)
        )
        SystemLogUtils.write_system_log_in_background(system_log_data)

        return response


    @staticmethod
    async def unhandled_exception(request: Request, exception: Exception) -> JSONResponse:
        """Log unhandled exceptions with the full traceback and return a generic 500."""
        logger.error(
            f'Unhandled exception in {request.method} {request.url.path}'
            , f'- {type(exception).__name__}: {exception}'
            , f'traceback: {"".join(traceback.format_exception(exception))}'
        )
        return JSONResponse(
            status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
            , content   = {'detail': 'Internal server error'}
        )


    @staticmethod
    async def validation_exception(request: Request, exception: RequestValidationError) -> JSONResponse:
        logger.warn(f'Validation error in {request.method} {request.url.path} - {exception.errors()}')
        return await request_validation_exception_handler(request, exception)


    @staticmethod
    async def http_exception(request: Request, exception: HTTPException) -> JSONResponse:
        log_method = logger.error if exception.status_code >= status.HTTP_500_INTERNAL_SERVER_ERROR else logger.warn
        log_method(f'HTTPException {exception.status_code} in {request.method} {request.url.path} - {exception.detail}')
        return JSONResponse(
            status_code = exception.status_code
            , content   = {'detail': exception.detail}
            , headers   = getattr(exception, 'headers', None)
        )
