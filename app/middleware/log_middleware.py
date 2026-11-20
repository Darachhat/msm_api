import traceback
from time   import perf_counter
from typing import Any, Optional

from fastapi              import Request, status
from fastapi.exceptions   import RequestValidationError
from fastapi.responses    import JSONResponse
from starlette.exceptions import HTTPException
from starlette.types      import ASGIApp, Receive, Scope, Send

from app.core.config               import settings
from app.core.constants            import CONTENT_TYPE_JSON, utc_now_naive
from app.core.enum                 import CHANNEL_ENUM, STATUS_CODE_ENUM, TRAFFIC_TYPE_ENUM
from app.core.log                  import logger
from app.core.system_log_utils     import SystemLogUtils
from app.schemas.base_schema       import IResponseBase, get_ulid
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


def _parse_request_bytes(body_bytes: bytes, content_type: Optional[str]) -> Optional[Any]:
    if not body_bytes:
        return None
    if content_type == 'multipart/form-data':
        return {'raw': f'<multipart/form-data, length: {len(body_bytes)}>'}
    if len(body_bytes) > settings.MAX_LOG_BODY_BYTES:
        return {'raw': f'<request body truncated, total length: {len(body_bytes)}>'}
    try:
        return SystemLogUtils.parse_body(body_bytes.decode('utf-8'))
    except UnicodeDecodeError:
        return {'raw': f'<binary data, length: {len(body_bytes)}>'}


def _parse_response_bytes(response_bytes: bytes, content_type: Optional[str]) -> Optional[Any]:
    if not response_bytes:
        return None
    lower_ct = (content_type or '').lower()
    if any(
        binary_hint in lower_ct
        for binary_hint in ('application/octet-stream', 'spreadsheetml', 'application/pdf', 'image/')
    ):
        return {'raw': f'<binary response ({content_type}), length: {len(response_bytes)}>'}
    if len(response_bytes) > settings.MAX_LOG_BODY_BYTES:
        return {'raw': f'<response body truncated, total length: {len(response_bytes)}>'}
    try:
        return SystemLogUtils.parse_body(response_bytes.decode('utf-8'))
    except UnicodeDecodeError:
        return {'raw': f'<binary response, length: {len(response_bytes)}>'}


def _make_replay_receive(raw_body: bytes, original_receive: Receive) -> Receive:
    body_sent = False

    async def _replay() -> dict:
        nonlocal body_sent
        if not body_sent:
            body_sent = True
            return {'type': 'http.request', 'body': raw_body, 'more_body': False}
        return await original_receive()

    return _replay


class LogMiddleware:
    """Pure ASGI inbound logging middleware (matching hub_api's BaseMiddleware).

    Streams responses directly without Starlette BaseHTTPMiddleware buffering/ExceptionGroup overhead,
    attaches X-Request-ID, writes access logs to logs/app.log, and dispatches INBOUND rows to track.system_log.
    """

    def __init__(self, app: ASGIApp) -> None:
        self.app = app


    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope['type'] != 'http':
            await self.app(scope, receive, send)
            return

        request      = Request(scope, receive)
        start_time   = perf_counter()
        req_datetime = utc_now_naive()
        request_id   = get_ulid()
        request.state.request_id = request_id

        header_content_type = request.headers.get('content-type') or ''
        content_type        = _parse_content_type(header_content_type)

        raw_request_body = b''
        if request.method in ('POST', 'PUT', 'PATCH'):
            try:
                raw_request_body = await request.body()
            except Exception as body_error:
                logger.warn(f'LogMiddleware: could not buffer request body: {str(body_error)}')
            receive = _make_replay_receive(raw_request_body, receive)

        response_status  : Optional[int]  = None
        response_headers : dict[str, str] = {}
        body_chunks      : list[bytes]    = []
        captured_bytes   : int            = 0
        is_text_or_json  : bool           = False

        async def capturing_send(message: dict) -> None:
            nonlocal response_status, response_headers, captured_bytes, is_text_or_json

            if message['type'] == 'http.response.start':
                response_status  = message.get('status')
                raw_headers      = list(message.get('headers', []))
                response_headers = {
                    k.decode('latin-1').lower(): v.decode('latin-1')
                    for k, v in raw_headers
                }
                resp_ct         = response_headers.get('content-type', '').lower()
                is_text_or_json = ('application/json' in resp_ct) or ('text/' in resp_ct)

                if 'x-request-id' not in response_headers:
                    raw_headers.append((b'x-request-id', request_id.encode('ascii')))
                    response_headers['x-request-id'] = request_id
                await send({**message, 'headers': raw_headers})
                return

            if message['type'] == 'http.response.body':
                chunk = message.get('body', b'')
                if chunk and is_text_or_json and captured_bytes <= settings.MAX_LOG_BODY_BYTES:
                    body_chunks.append(chunk)
                    captured_bytes += len(chunk)

            await send(message)

        try:
            await self.app(scope, receive, capturing_send)
        finally:
            try:
                res_datetime     = utc_now_naive()
                duration_seconds = round(perf_counter() - start_time, 4)
                duration_ms      = round(duration_seconds * 1000, 2)
                client_ip        = request.client.host if request.client else None

                parsed_request_body = _parse_request_bytes(raw_request_body, content_type)
                if request.query_params:
                    query_dict = dict(request.query_params)
                    if parsed_request_body is None:
                        parsed_request_body = query_dict
                    elif isinstance(parsed_request_body, dict):
                        parsed_request_body = {**query_dict, **parsed_request_body}

                response_bytes       = b''.join(body_chunks) if is_text_or_json else b''
                parsed_response_body = _parse_response_bytes(
                    response_bytes
                    , response_headers.get('content-type')
                )

                trace_id = request_id
                if isinstance(parsed_response_body, dict) and parsed_response_body.get('trace_id'):
                    trace_id = str(parsed_response_body['trace_id']).strip()

                auth_context = getattr(request.state, 'auth_context', None)
                system_code  = (
                    auth_context.system_code
                    if auth_context
                    else (getattr(request.state, 'system_code', None) or 'MSM_API')
                )
                channel      = (
                    auth_context.channel
                    if auth_context
                    else (getattr(request.state, 'channel', None) or CHANNEL_ENUM.API.value)
                )
                actor_name   = auth_context.username if auth_context else None
                status_val   = response_status or status.HTTP_500_INTERNAL_SERVER_ERROR

                access_message = (
                    f'{request.method} {request.url.path} {status_val} '
                    f'{duration_ms}ms system: {system_code} user: {actor_name or "-"} ip: {client_ip or "N/A"}'
                )
                if status_val >= status.HTTP_500_INTERNAL_SERVER_ERROR:
                    logger.error(access_message)
                elif status_val >= status.HTTP_400_BAD_REQUEST:
                    logger.warn(access_message)
                else:
                    logger.info(access_message)

                SystemLogUtils.write_system_log_in_background(
                    SYSTEM_LOG_DATA(
                        traffic_type           = TRAFFIC_TYPE_ENUM.INBOUND.value
                        , system_code          = system_code
                        , channel              = channel
                        , request_method       = request.method
                        , request_endpoint     = str(request.url.path)
                        , request_netloc       = f'{request.url.scheme}://{request.url.netloc}' if request.url.netloc else None
                        , request_content_type = content_type
                        , request_user_agent   = request.headers.get('user-agent')
                        , request_headers      = SystemLogUtils.sanitize_headers(dict(request.headers))
                        , request_body         = parsed_request_body
                        , requested_datetime   = req_datetime
                        , client_ip            = client_ip
                        , response_code        = status_val
                        , response_headers     = SystemLogUtils.sanitize_headers(response_headers)
                        , response_body        = parsed_response_body
                        , response_duration    = duration_seconds
                        , response_datetime    = res_datetime
                        , client_log_id        = trace_id
                        , status_code          = STATUS_CODE_ENUM.ACTIVE.value
                        , created_datetime     = res_datetime
                    )
                )
            except Exception as log_error:
                logger.error(f'LogMiddleware: failed to persist inbound log: {str(log_error)}')


    @staticmethod
    async def unhandled_exception(request: Request, exception: Exception) -> JSONResponse:
        """Log unhandled exceptions with full traceback and return a uniform IResponseBase 500."""
        trace_id = getattr(request.state, 'request_id', None) or get_ulid()
        logger.error(
            f'Unhandled exception in {request.method} {request.url.path}'
            , f'- {type(exception).__name__}: {exception}'
            , f'traceback: {"".join(traceback.format_exception(exception))}'
        )
        return JSONResponse(
            status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
            , content   = IResponseBase(
                trace_id  = trace_id
                , status  = 0
                , message = 'Internal server error'
                , data    = None
            ).model_dump()
            , headers   = {'X-Request-ID': trace_id}
        )


    @staticmethod
    async def validation_exception(request: Request, exception: RequestValidationError) -> JSONResponse:
        trace_id = getattr(request.state, 'request_id', None) or get_ulid()
        errors   = exception.errors()
        logger.warn(f'Validation error in {request.method} {request.url.path} - {errors}')
        return JSONResponse(
            status_code = status.HTTP_422_UNPROCESSABLE_ENTITY
            , content   = IResponseBase(
                trace_id  = trace_id
                , status  = 0
                , message = 'Validation error'
                , data    = errors
            ).model_dump()
            , headers   = {'X-Request-ID': trace_id}
        )


    @staticmethod
    async def http_exception(request: Request, exception: HTTPException) -> JSONResponse:
        trace_id   = getattr(request.state, 'request_id', None) or get_ulid()
        log_method = logger.error if exception.status_code >= status.HTTP_500_INTERNAL_SERVER_ERROR else logger.warn
        log_method(f'HTTPException {exception.status_code} in {request.method} {request.url.path} - {exception.detail}')

        headers = dict(getattr(exception, 'headers', None) or {})
        headers.setdefault('X-Request-ID', trace_id)
        return JSONResponse(
            status_code = exception.status_code
            , content   = IResponseBase(
                trace_id  = trace_id
                , status  = 0
                , message = str(exception.detail)
                , data    = None
            ).model_dump()
            , headers   = headers
        )
