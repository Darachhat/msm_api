import json
from datetime import datetime
from time     import perf_counter

from app.core.constants import PHNOM_PENH_TZ
from app.core.log       import logger, trace_logger

# Credential headers are masked so session tokens never land in a log file
_TRACE_MASKED_HEADERS = {'authorization', 'proxy-authorization', 'cookie', 'x-api-key'}


class TraceMiddleware:
    """Pure ASGI, registered outermost: traces every request, including 404 scans,
    CORS preflights and requests that crash before reaching a route."""

    def __init__(self, app):
        self.app = app


    async def __call__(self, scope, receive, send):
        if scope['type'] != 'http':
            await self.app(scope, receive, send)
            return

        request_datetime   = datetime.now(PHNOM_PENH_TZ)
        start_time         = perf_counter()
        response           = {'status': None, 'bytes': None}
        has_content_length = False
        error              = None

        async def send_wrapper(message):
            nonlocal has_content_length
            if message['type'] == 'http.response.start':
                response['status'] = message['status']
                for name, value in message.get('headers', []):
                    if name.lower() == b'content-length' and value.isdigit():
                        response['bytes']  = int(value)
                        has_content_length = True
            elif message['type'] == 'http.response.body' and not has_content_length:
                response['bytes'] = (response['bytes'] or 0) + len(message.get('body', b''))
            await send(message)

        try:
            await self.app(scope, receive, send_wrapper)
        except BaseException as exception:
            error = f'{type(exception).__name__}: {exception}'
            raise
        finally:
            try:
                TraceMiddleware._write(scope, request_datetime, perf_counter() - start_time, response, error)
            except Exception as trace_error:
                logger.error(f'TraceMiddleware write failed: {str(trace_error)}')


    @staticmethod
    def _write(scope, request_datetime, duration, response, error) -> None:
        headers = {}
        for raw_name, raw_value in scope.get('headers', []):
            name  = raw_name.decode('latin-1').lower()
            value = '***' if name in _TRACE_MASKED_HEADERS else raw_value.decode('latin-1')[:2000]
            headers[name] = f'{headers[name]}, {value}' if name in headers else value

        client = scope.get('client') or (None, None)
        server = scope.get('server')

        trace_logger.info(json.dumps({
            'ts'                : request_datetime.isoformat(timespec='milliseconds')
            , 'client_ip'       : client[0]
            , 'client_port'     : client[1]
            , 'x_forwarded_for' : headers.get('x-forwarded-for')
            , 'x_real_ip'       : headers.get('x-real-ip')
            , 'forwarded'       : headers.get('forwarded')
            , 'server'          : f'{server[0]}:{server[1]}' if server else None
            , 'method'          : scope.get('method')
            , 'scheme'          : scope.get('scheme')
            , 'http_version'    : scope.get('http_version')
            , 'host'            : headers.get('host')
            , 'path'            : scope.get('path')
            , 'query'           : scope.get('query_string', b'').decode('latin-1')[:2000]
            , 'route'           : getattr(scope.get('route'), 'path', None)
            , 'status'          : response['status'] or (500 if error else None)
            , 'duration_ms'     : round(duration * 1000, 2)
            , 'response_bytes'  : response['bytes']
            , 'user_agent'      : headers.get('user-agent')
            , 'referer'         : headers.get('referer')
            , 'origin'          : headers.get('origin')
            , 'accept_language' : headers.get('accept-language')
            , 'content_type'    : headers.get('content-type')
            , 'content_length'  : headers.get('content-length')
            , 'error'           : error
            , 'headers'         : headers
        }, ensure_ascii=False, default=str))
