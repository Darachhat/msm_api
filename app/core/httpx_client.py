import asyncio
import concurrent.futures
import threading
from contextvars import ContextVar
from datetime    import datetime, timezone
from typing      import Any, Dict, Optional, Union

import httpx
from fastapi        import Request
from sqlalchemy.orm import Session

from app.core.log              import logger
from app.core.system_log_utils import SystemLogUtils

# Global fallback client (set during app startup)
_global_httpx_client      : Optional[httpx.AsyncClient]              = None
_global_httpx_client_lock                                            = threading.Lock()
_asyncio_run_client       : ContextVar[Optional[httpx.AsyncClient]]  = ContextVar('asyncio_run_client', default=None)


def create_httpx_client() -> httpx.AsyncClient:
    return httpx.AsyncClient(
        verify             = True
        , timeout          = httpx.Timeout(30.0, connect=10.0)
        , follow_redirects = True
    )


def set_global_httpx_client(client: Optional[httpx.AsyncClient]) -> None:
    global _global_httpx_client
    _global_httpx_client = client


def async_run(coroutine):
    """Run an async coroutine from synchronous code with proper httpx client cleanup."""
    async def _wrapper():
        try:
            return await coroutine
        finally:
            client = _asyncio_run_client.get()
            if client:
                try:
                    await client.aclose()
                except Exception:
                    pass
                _asyncio_run_client.set(None)

    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None

    if loop and loop.is_running():
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
            return executor.submit(asyncio.run, _wrapper()).result()

    return asyncio.run(_wrapper())


def get_httpx_client(request: Optional[Request] = None) -> httpx.AsyncClient:
    if request and hasattr(request.app.state, 'httpx_client'):
        client = request.app.state.httpx_client
        if client:
            return client

    try:
        client = _asyncio_run_client.get()
        if client is None:
            client = create_httpx_client()
            _asyncio_run_client.set(client)
        return client
    except RuntimeError:
        pass

    if _global_httpx_client:
        return _global_httpx_client

    if request is None:
        with _global_httpx_client_lock:
            if _global_httpx_client:
                return _global_httpx_client

            logger.warn(
                'httpx.AsyncClient was not initialized by lifespan. '
                'Creating client lazily as fallback.'
            )
            client = create_httpx_client()
            set_global_httpx_client(client)
            return client

    raise RuntimeError(
        'httpx.AsyncClient not initialized. '
        'Ensure the FastAPI app lifespan has started.'
    )


def _serialize_request_body(
    json_payload : Optional[Any]
    , data       : Optional[Any]
    , files      : Optional[Any]
    , params     : Optional[Dict[str, Any]]
) -> Any:
    """Build a JSON-serializable audit representation of the outbound request payload."""
    logged_body = json_payload
    if logged_body is None:
        if data is not None:
            logged_body = dict(data) if isinstance(data, dict) else str(data)

        if files is not None:
            files_metadata: Dict[str, str] = {}
            if isinstance(files, dict):
                for file_key, file_value in files.items():
                    if isinstance(file_value, tuple) and len(file_value) > 0:
                        files_metadata[str(file_key)] = str(file_value[0])
                    elif hasattr(file_value, 'name'):
                        files_metadata[str(file_key)] = str(file_value.name)
                    else:
                        files_metadata[str(file_key)] = '[FILE]'
            elif isinstance(files, (list, tuple)):
                for item in files:
                    if isinstance(item, tuple) and len(item) >= 2:
                        file_key   = str(item[0])
                        file_value = item[1]
                        if isinstance(file_value, tuple) and len(file_value) > 0:
                            files_metadata[file_key] = str(file_value[0])
                        else:
                            files_metadata[file_key] = '[FILE]'

            if isinstance(logged_body, dict):
                logged_body = {
                    **logged_body
                    , '_files': files_metadata
                }
            else:
                logged_body = {'_files': files_metadata}

    if params is not None:
        params_dict = dict(params) if isinstance(params, dict) else {'_params': params}
        if logged_body is None:
            logged_body = params_dict
        elif isinstance(logged_body, dict):
            logged_body = {**params_dict, **logged_body}
        else:
            logged_body = {**params_dict, '_body': logged_body}

    return logged_body


class HttpClient:

    @staticmethod
    async def request(
        method          : str
        , url           : str
        , system_code   : str
        , headers       : Optional[Dict[str, str]]             = None
        , params        : Optional[Dict[str, Any]]             = None
        , json          : Optional[Any]                        = None
        , data          : Optional[Any]                        = None
        , files         : Optional[Any]                        = None
        , timeout       : Optional[Union[float, httpx.Timeout]] = None
        , client_log_id : Optional[str]                        = None
        , channel       : Optional[str]                        = None
        , session       : Optional[Session]                    = None
        , client        : Optional[httpx.AsyncClient]          = None
    ) -> httpx.Response:
        """Execute an asynchronous HTTP request with automatic OUTBOUND audit logging."""
        method_upper       = method.upper()
        requested_datetime = datetime.now(timezone.utc)

        if timeout is None:
            timeout_config = httpx.Timeout(30.0, connect=10.0)
        elif isinstance(timeout, (int, float)):
            timeout_config = httpx.Timeout(float(timeout), connect=10.0)
        elif isinstance(timeout, httpx.Timeout):
            timeout_config = timeout
        else:
            timeout_config = httpx.Timeout(30.0, connect=10.0)

        logged_request_body = _serialize_request_body(
            json_payload = json
            , data       = data
            , files      = files
            , params     = params
        )

        try:
            active_client = client or _global_httpx_client
            if active_client is not None:
                response = await active_client.request(
                    method    = method_upper
                    , url     = url
                    , headers = headers
                    , params  = params
                    , json    = json
                    , data    = data
                    , files   = files
                    , timeout = timeout_config
                )
            else:
                async with httpx.AsyncClient(
                    verify             = True
                    , timeout          = timeout_config
                    , follow_redirects = True
                ) as temporary_client:
                    response = await temporary_client.request(
                        method    = method_upper
                        , url     = url
                        , headers = headers
                        , params  = params
                        , json    = json
                        , data    = data
                        , files   = files
                    )

            responded_datetime = datetime.now(timezone.utc)

            try:
                response_body_log = response.json()
            except Exception:
                response_body_log = response.text[:500] if hasattr(response, 'text') else str(response.content)[:500]

            SystemLogUtils.store_outgoing_log(
                system_code          = system_code
                , request_endpoint   = url
                , request_body       = logged_request_body
                , requested_datetime = requested_datetime
                , response_code      = response.status_code
                , response_headers   = dict(response.headers)
                , response_body      = response_body_log
                , response_datetime  = responded_datetime
                , request_method     = method_upper
                , client_log_id      = client_log_id
                , channel            = channel
                , request_headers    = headers
            )

            return response

        except httpx.TimeoutException as timeout_error:
            responded_datetime = datetime.now(timezone.utc)
            SystemLogUtils.store_outgoing_log(
                system_code          = system_code
                , request_endpoint   = url
                , request_body       = logged_request_body
                , requested_datetime = requested_datetime
                , response_code      = 504
                , response_body      = str(timeout_error)[:500]
                , response_datetime  = responded_datetime
                , request_method     = method_upper
                , client_log_id      = client_log_id
                , channel            = channel
                , request_headers    = headers
            )
            logger.error(
                'HttpClient.request: Timeout error'
                , f'method: {method_upper}'
                , f'url: {url}'
                , f'system_code: {system_code}'
                , f'client_log_id: {client_log_id}'
                , f'error: {str(timeout_error)}'
            )
            raise

        except Exception as request_error:
            responded_datetime = datetime.now(timezone.utc)
            SystemLogUtils.store_outgoing_log(
                system_code          = system_code
                , request_endpoint   = url
                , request_body       = logged_request_body
                , requested_datetime = requested_datetime
                , response_code      = 503
                , response_body      = str(request_error)[:500]
                , response_datetime  = responded_datetime
                , request_method     = method_upper
                , client_log_id      = client_log_id
                , channel            = channel
                , request_headers    = headers
            )
            logger.error(
                'HttpClient.request: Request error'
                , f'method: {method_upper}'
                , f'url: {url}'
                , f'system_code: {system_code}'
                , f'client_log_id: {client_log_id}'
                , f'error: {str(request_error)}'
            )
            raise


    @staticmethod
    async def get(
        url             : str
        , system_code   : str
        , headers       : Optional[Dict[str, str]]             = None
        , params        : Optional[Dict[str, Any]]             = None
        , timeout       : Optional[Union[float, httpx.Timeout]] = None
        , client_log_id : Optional[str]                        = None
        , channel       : Optional[str]                        = None
        , session       : Optional[Session]                    = None
        , client        : Optional[httpx.AsyncClient]          = None
    ) -> httpx.Response:
        return await HttpClient.request(
            method          = 'GET'
            , url           = url
            , system_code   = system_code
            , headers       = headers
            , params        = params
            , timeout       = timeout
            , client_log_id = client_log_id
            , channel       = channel
            , session       = session
            , client        = client
        )


    @staticmethod
    async def post(
        url             : str
        , system_code   : str
        , headers       : Optional[Dict[str, str]]             = None
        , params        : Optional[Dict[str, Any]]             = None
        , json          : Optional[Any]                        = None
        , data          : Optional[Any]                        = None
        , files         : Optional[Any]                        = None
        , timeout       : Optional[Union[float, httpx.Timeout]] = None
        , client_log_id : Optional[str]                        = None
        , channel       : Optional[str]                        = None
        , session       : Optional[Session]                    = None
        , client        : Optional[httpx.AsyncClient]          = None
    ) -> httpx.Response:
        return await HttpClient.request(
            method          = 'POST'
            , url           = url
            , system_code   = system_code
            , headers       = headers
            , params        = params
            , json          = json
            , data          = data
            , files         = files
            , timeout       = timeout
            , client_log_id = client_log_id
            , channel       = channel
            , session       = session
            , client        = client
        )


    @staticmethod
    async def put(
        url             : str
        , system_code   : str
        , headers       : Optional[Dict[str, str]]             = None
        , params        : Optional[Dict[str, Any]]             = None
        , json          : Optional[Any]                        = None
        , data          : Optional[Any]                        = None
        , files         : Optional[Any]                        = None
        , timeout       : Optional[Union[float, httpx.Timeout]] = None
        , client_log_id : Optional[str]                        = None
        , channel       : Optional[str]                        = None
        , session       : Optional[Session]                    = None
        , client        : Optional[httpx.AsyncClient]          = None
    ) -> httpx.Response:
        return await HttpClient.request(
            method          = 'PUT'
            , url           = url
            , system_code   = system_code
            , headers       = headers
            , params        = params
            , json          = json
            , data          = data
            , files         = files
            , timeout       = timeout
            , client_log_id = client_log_id
            , channel       = channel
            , session       = session
            , client        = client
        )


    @staticmethod
    async def delete(
        url             : str
        , system_code   : str
        , headers       : Optional[Dict[str, str]]             = None
        , params        : Optional[Dict[str, Any]]             = None
        , timeout       : Optional[Union[float, httpx.Timeout]] = None
        , client_log_id : Optional[str]                        = None
        , channel       : Optional[str]                        = None
        , session       : Optional[Session]                    = None
        , client        : Optional[httpx.AsyncClient]          = None
    ) -> httpx.Response:
        return await HttpClient.request(
            method          = 'DELETE'
            , url           = url
            , system_code   = system_code
            , headers       = headers
            , params        = params
            , timeout       = timeout
            , client_log_id = client_log_id
            , channel       = channel
            , session       = session
            , client        = client
        )
