import ast
from concurrent.futures import ThreadPoolExecutor
from datetime           import datetime, timezone
import json
from typing             import Any, Dict, Optional, Union
from urllib.parse       import urlparse

from app.core.constants            import REDACTED_BODY_KEYS, REDACTED_HEADER_KEYS
from app.core.db                   import getStaticSession
from app.core.enum                 import CHANNEL_ENUM, STATUS_CODE_ENUM, TRAFFIC_TYPE_ENUM
from app.core.log                  import logger
from app.models.track_model        import SYSTEM_LOG_MODEL
from app.schemas.base_schema       import get_ulid
from app.schemas.system_log_schema import SYSTEM_LOG_DATA

_LOG_EXECUTOR = ThreadPoolExecutor(max_workers = 1, thread_name_prefix = "system-log")


class SystemLogUtils:

    @staticmethod
    def sanitize_headers(headers: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        """Redact sensitive header values before persisting to track.system_log."""
        if not headers or not isinstance(headers, dict):
            return None
        return {
            key: ('***REDACTED***' if str(key).lower() in REDACTED_HEADER_KEYS else value)
            for key, value in headers.items()
        }


    @staticmethod
    def sanitize_body(data: Any) -> Any:
        """Recursively redact sensitive keys in JSON request/response bodies."""
        if isinstance(data, dict):
            return {
                key: (
                    '***REDACTED***'
                    if str(key).lower() in REDACTED_BODY_KEYS
                    else SystemLogUtils.sanitize_body(value)
                )
                for key, value in data.items()
            }
        if isinstance(data, list):
            return [SystemLogUtils.sanitize_body(item) for item in data]
        return data


    @staticmethod
    def parse_body(data: Any) -> Optional[Any]:
        """Safely parse dict, list, JSON string, or Python literal to a JSONB-safe object."""
        if data is None:
            return None
        if isinstance(data, (dict, list)):
            return SystemLogUtils.sanitize_body(data)
        if isinstance(data, str):
            text = data.strip()
            if not text:
                return None
            if (text.startswith('{') and text.endswith('}')) or (text.startswith('[') and text.endswith(']')):
                try:
                    return SystemLogUtils.sanitize_body(json.loads(text))
                except Exception:
                    try:
                        evaluated = ast.literal_eval(text)
                        if isinstance(evaluated, (dict, list)):
                            return SystemLogUtils.sanitize_body(evaluated)
                    except Exception:
                        pass
            return {'raw': text}
        return {'raw': str(data)}


    @staticmethod
    def _save_system_log(system_log_data: Union[SYSTEM_LOG_DATA, dict]) -> None:
        """Save a system_log entry synchronously using a dedicated static DB session."""
        try:
            payload = (
                system_log_data.model_dump()
                if isinstance(system_log_data, SYSTEM_LOG_DATA)
                else system_log_data
            )
            session = getStaticSession()
            try:
                record = SYSTEM_LOG_MODEL(**payload)
                session.add(record)
                session.commit()
            finally:
                session.close()
        except Exception as save_error:
            logger.error(f'SystemLogUtils._save_system_log Exception: {str(save_error)}')


    @staticmethod
    def write_system_log_in_background(system_log_data: Union[SYSTEM_LOG_DATA, dict]) -> None:
        """Queue system_log persistence on a single background worker to avoid DB connection spikes."""
        _LOG_EXECUTOR.submit(SystemLogUtils._save_system_log, system_log_data)


    @staticmethod
    def store_outgoing_log(
        system_code          : str
        , request_endpoint   : str
        , request_body       : Any
        , requested_datetime : Optional[datetime]       = None
        , response_code      : Optional[int]            = None
        , response_headers   : Optional[Dict[str, str]] = None
        , response_body      : Any                      = None
        , response_datetime  : Optional[datetime]       = None
        , client_log_id      : Optional[str]            = None
        , request_method     : str                      = 'POST'
        , channel            : Optional[str]            = None
        , request_headers    : Optional[Dict[str, str]] = None
    ) -> None:
        """Build and asynchronously persist an OUTBOUND API audit log into track.system_log."""
        try:
            req_dt = requested_datetime or datetime.now(timezone.utc)
            res_dt = response_datetime  or datetime.now(timezone.utc)

            parsed_request_body  = SystemLogUtils.parse_body(request_body)
            parsed_response_body = SystemLogUtils.parse_body(response_body)

            parsed_response_code = (
                int(response_code)
                if (response_code is not None and str(response_code).isdigit())
                else None
            )
            duration = round((res_dt - req_dt).total_seconds(), 4) if (req_dt and res_dt) else None

            clean_endpoint = request_endpoint
            request_netloc = None
            if request_endpoint:
                parsed_url = urlparse(request_endpoint)
                if parsed_url.scheme in ('http', 'https'):
                    clean_endpoint = parsed_url.path or request_endpoint
                    request_netloc = f'{parsed_url.scheme}://{parsed_url.netloc}' if parsed_url.netloc else None

            sanitized_request_headers  = SystemLogUtils.sanitize_headers(request_headers)
            sanitized_response_headers = SystemLogUtils.sanitize_headers(response_headers)
            request_content_type       = None
            request_user_agent         = None
            if request_headers and isinstance(request_headers, dict):
                request_content_type = request_headers.get('Content-Type') or request_headers.get('content-type')
                request_user_agent   = request_headers.get('User-Agent')   or request_headers.get('user-agent')

            system_log_data = SYSTEM_LOG_DATA(
                traffic_type           = TRAFFIC_TYPE_ENUM.OUTBOUND.value
                , system_code          = system_code
                , channel              = channel or CHANNEL_ENUM.SYSTEM.value
                , request_method       = request_method
                , request_endpoint     = clean_endpoint
                , request_netloc       = request_netloc
                , request_content_type = request_content_type
                , request_user_agent   = request_user_agent
                , request_headers      = sanitized_request_headers
                , request_body         = parsed_request_body
                , requested_datetime   = req_dt.replace(tzinfo=None)
                , response_code        = parsed_response_code
                , response_headers     = sanitized_response_headers
                , response_body        = parsed_response_body
                , response_duration    = duration
                , response_datetime    = res_dt.replace(tzinfo=None)
                , client_log_id        = client_log_id or get_ulid()
                , status_code          = STATUS_CODE_ENUM.ACTIVE.value
                , created_datetime     = req_dt.replace(tzinfo=None)
            )

            SystemLogUtils.write_system_log_in_background(system_log_data)
        except Exception as dispatch_error:
            logger.error(f'SystemLogUtils.store_outgoing_log Exception: {str(dispatch_error)}')
