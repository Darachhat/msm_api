import base64
from typing import Dict, Optional, Tuple
from uuid   import UUID

import jwt
from fastapi             import Request, status
from fastapi.concurrency import run_in_threadpool
from fastapi.responses   import JSONResponse
from sqlalchemy.orm      import Session
from starlette.types     import ASGIApp, Receive, Scope, Send

from app.core.constants        import utc_now_naive
from app.core.db               import getStaticSession
from app.core.enum             import AUTH_TYPE_ENUM, CHANNEL_ENUM, STATUS_CODE_ENUM, TRAFFIC_TYPE_ENUM
from app.core.log              import logger
from app.core.security         import decode_token
from app.core.system_log_utils import SystemLogUtils
from app.middleware.types      import AuthContext
from app.schemas.base_schema   import IResponseBase, get_ulid
from app.schemas.system_log_schema import SYSTEM_LOG_DATA
from app.models.auth_model import (
    CREDENTIAL_API_KEY_MODEL
    , CREDENTIAL_BASIC_MODEL
    , CREDENTIAL_BEARER_MODEL
    , SYSTEM_CREDENTIAL_MODEL
    , SYSTEM_MODEL
    , USER_MODEL
)

_SUPPORTED_AUTH_TYPES = frozenset({
    AUTH_TYPE_ENUM.API_KEY.value
    , AUTH_TYPE_ENUM.BEARER.value
    , AUTH_TYPE_ENUM.BASIC.value
})


def _unauthorized_json(request: Request, detail: str) -> JSONResponse:
    trace_id = get_ulid()
    now_utc  = utc_now_naive()
    body     = IResponseBase(
        trace_id  = trace_id
        , status  = 0
        , message = detail
        , data    = None
    ).model_dump()

    # Audit rejected 401 attempts into track.system_log as well
    SystemLogUtils.write_system_log_in_background(
        SYSTEM_LOG_DATA(
            traffic_type           = TRAFFIC_TYPE_ENUM.INBOUND.value
            , system_code          = "UNAUTHENTICATED"
            , channel              = CHANNEL_ENUM.API.value
            , request_method       = request.method
            , request_endpoint     = str(request.url.path)
            , request_netloc       = f"{request.url.scheme}://{request.url.netloc}" if request.url.netloc else None
            , request_content_type = request.headers.get("content-type")
            , request_user_agent   = request.headers.get("user-agent")
            , request_headers      = SystemLogUtils.sanitize_headers(dict(request.headers))
            , requested_datetime   = now_utc
            , client_ip            = request.client.host if request.client else None
            , response_code        = status.HTTP_401_UNAUTHORIZED
            , response_body        = body
            , response_duration    = 0.0
            , response_datetime    = now_utc
            , client_log_id        = trace_id
            , status_code          = STATUS_CODE_ENUM.ACTIVE.value
            , created_datetime     = now_utc
        )
    )
    return JSONResponse(
        status_code = status.HTTP_401_UNAUTHORIZED
        , content   = body
        , headers   = {
            "WWW-Authenticate" : "Bearer"
            , "X-Request-ID"   : trace_id
        }
    )


def _verify_system_credential(
    session      : Session
    , auth_type  : str
    , auth_value : str
) -> Optional[tuple]:
    """Verify an INBOUND system credential against auth.system + auth.system_credential + credential_*."""
    base_query = (
        session.query(SYSTEM_CREDENTIAL_MODEL, SYSTEM_MODEL)
        .join(
            SYSTEM_MODEL
            , (SYSTEM_MODEL.code == SYSTEM_CREDENTIAL_MODEL.system_code)
            & (SYSTEM_MODEL.status_code == STATUS_CODE_ENUM.ACTIVE.value)
            & (SYSTEM_MODEL.deleted_datetime.is_(None))
        )
        .filter(
            SYSTEM_CREDENTIAL_MODEL.auth_type_code == auth_type
            , SYSTEM_CREDENTIAL_MODEL.traffic_type == TRAFFIC_TYPE_ENUM.INBOUND.value
            , SYSTEM_CREDENTIAL_MODEL.status_code == STATUS_CODE_ENUM.ACTIVE.value
            , SYSTEM_CREDENTIAL_MODEL.deleted_datetime.is_(None)
        )
    )

    if auth_type == AUTH_TYPE_ENUM.BEARER.value:
        return (
            base_query
            .join(
                CREDENTIAL_BEARER_MODEL
                , (CREDENTIAL_BEARER_MODEL.system_code == SYSTEM_CREDENTIAL_MODEL.system_code)
                & (CREDENTIAL_BEARER_MODEL.traffic_type == TRAFFIC_TYPE_ENUM.INBOUND.value)
                & (CREDENTIAL_BEARER_MODEL.token_value == auth_value)
                & (CREDENTIAL_BEARER_MODEL.status_code == STATUS_CODE_ENUM.ACTIVE.value)
                & (CREDENTIAL_BEARER_MODEL.deleted_datetime.is_(None))
            )
            .first()
        )

    if auth_type == AUTH_TYPE_ENUM.API_KEY.value:
        return (
            base_query
            .join(
                CREDENTIAL_API_KEY_MODEL
                , (CREDENTIAL_API_KEY_MODEL.system_code == SYSTEM_CREDENTIAL_MODEL.system_code)
                & (CREDENTIAL_API_KEY_MODEL.traffic_type == TRAFFIC_TYPE_ENUM.INBOUND.value)
                & (CREDENTIAL_API_KEY_MODEL.key_value == auth_value)
                & (CREDENTIAL_API_KEY_MODEL.status_code == STATUS_CODE_ENUM.ACTIVE.value)
                & (CREDENTIAL_API_KEY_MODEL.deleted_datetime.is_(None))
            )
            .first()
        )

    if auth_type == AUTH_TYPE_ENUM.BASIC.value:
        try:
            decoded               = base64.b64decode(auth_value, validate=True).decode("utf-8")
            username, _, password = decoded.partition(":")
        except Exception:
            return None
        return (
            base_query
            .join(
                CREDENTIAL_BASIC_MODEL
                , (CREDENTIAL_BASIC_MODEL.system_code == SYSTEM_CREDENTIAL_MODEL.system_code)
                & (CREDENTIAL_BASIC_MODEL.traffic_type == TRAFFIC_TYPE_ENUM.INBOUND.value)
                & (CREDENTIAL_BASIC_MODEL.username == username)
                & (CREDENTIAL_BASIC_MODEL.password == password)
                & (CREDENTIAL_BASIC_MODEL.status_code == STATUS_CODE_ENUM.ACTIVE.value)
                & (CREDENTIAL_BASIC_MODEL.deleted_datetime.is_(None))
            )
            .first()
        )

    return None


def get_outbound_auth_headers(session: Session, system_code: str) -> Dict[str, str]:
    """Resolve OUTBOUND auth headers for a target system_code from auth.system_credential."""
    cred = (
        session.query(SYSTEM_CREDENTIAL_MODEL)
        .filter(
            SYSTEM_CREDENTIAL_MODEL.system_code == system_code
            , SYSTEM_CREDENTIAL_MODEL.traffic_type == TRAFFIC_TYPE_ENUM.OUTBOUND.value
            , SYSTEM_CREDENTIAL_MODEL.status_code == STATUS_CODE_ENUM.ACTIVE.value
            , SYSTEM_CREDENTIAL_MODEL.deleted_datetime.is_(None)
        )
        .first()
    )
    if not cred:
        return {}

    if cred.auth_type_code == AUTH_TYPE_ENUM.API_KEY.value:
        row = (
            session.query(CREDENTIAL_API_KEY_MODEL)
            .filter(
                CREDENTIAL_API_KEY_MODEL.system_code == system_code
                , CREDENTIAL_API_KEY_MODEL.traffic_type == TRAFFIC_TYPE_ENUM.OUTBOUND.value
                , CREDENTIAL_API_KEY_MODEL.status_code == STATUS_CODE_ENUM.ACTIVE.value
                , CREDENTIAL_API_KEY_MODEL.deleted_datetime.is_(None)
            )
            .first()
        )
        if row and row.key_location == "header":
            return {row.key_name: row.key_value}

    if cred.auth_type_code == AUTH_TYPE_ENUM.BEARER.value:
        row = (
            session.query(CREDENTIAL_BEARER_MODEL)
            .filter(
                CREDENTIAL_BEARER_MODEL.system_code == system_code
                , CREDENTIAL_BEARER_MODEL.traffic_type == TRAFFIC_TYPE_ENUM.OUTBOUND.value
                , CREDENTIAL_BEARER_MODEL.status_code == STATUS_CODE_ENUM.ACTIVE.value
                , CREDENTIAL_BEARER_MODEL.deleted_datetime.is_(None)
            )
            .first()
        )
        if row:
            prefix = f"{row.token_prefix} " if row.token_prefix else ""
            return {row.header_name: f"{prefix}{row.token_value}"}

    if cred.auth_type_code == AUTH_TYPE_ENUM.BASIC.value:
        row = (
            session.query(CREDENTIAL_BASIC_MODEL)
            .filter(
                CREDENTIAL_BASIC_MODEL.system_code == system_code
                , CREDENTIAL_BASIC_MODEL.traffic_type == TRAFFIC_TYPE_ENUM.OUTBOUND.value
                , CREDENTIAL_BASIC_MODEL.status_code == STATUS_CODE_ENUM.ACTIVE.value
                , CREDENTIAL_BASIC_MODEL.deleted_datetime.is_(None)
            )
            .first()
        )
        if row:
            encoded = base64.b64encode(f"{row.username}:{row.password}".encode("utf-8")).decode("ascii")
            return {"Authorization": f"Basic {encoded}"}

    return {}


class AuthMiddleware:
    """Pure ASGI authentication middleware (following hub_api's SystemAuthMiddleware).

    Runs before LogMiddleware so every inbound request has request.state.auth_context
    resolved for both RBAC dependencies and track.system_log auditing.
    """

    SKIP_PREFIXES = (
        "/docs"
        , "/redoc"
        , "/openapi.json"
        , "/health"
        , "/api/v1/auth/login"
        , "/api/v1/auth/refresh"
        , "/api/v1/auth/logout"
        , "/api/v1/auth/forgot-password"
        , "/api/v1/auth/reset-password"
        , "/api/v1/files/preview/"
        , "/api/v1/files/download/"
    )

    def __init__(self, app: ASGIApp) -> None:
        self.app = app


    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        # Always let CORS preflight requests through
        if scope.get("method") == "OPTIONS":
            await self.app(scope, receive, send)
            return

        request = Request(scope, receive)
        path    = request.url.path

        if not path.startswith("/api/v1/") or any(path.startswith(prefix) for prefix in self.SKIP_PREFIXES):
            await self.app(scope, receive, send)
            return

        auth_type, auth_value = self._extract_auth(request)
        if not auth_type or not auth_value:
            logger.warn(f"AuthMiddleware: missing auth header for '{path}'")
            await _unauthorized_json(request, "Missing or unrecognized authentication header.")(scope, receive, send)
            return

        client_type = (request.headers.get("X-Client-Type") or "web").strip().lower()
        try:
            auth_context = await run_in_threadpool(
                self._resolve_auth
                , auth_type
                , auth_value
                , client_type
            )
        except Exception as auth_error:
            logger.error(f"AuthMiddleware: resolution error for '{path}': {str(auth_error)}")
            trace_id = get_ulid()
            await JSONResponse(
                status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
                , content   = IResponseBase(
                    trace_id  = trace_id
                    , status  = 0
                    , message = "Internal server error"
                    , data    = None
                ).model_dump()
                , headers   = {"X-Request-ID": trace_id}
            )(scope, receive, send)
            return

        if auth_context is None:
            logger.warn(f"AuthMiddleware: invalid or revoked credential for '{path}'")
            await _unauthorized_json(request, "Invalid, expired, or revoked credentials.")(scope, receive, send)
            return

        request.state.auth_context = auth_context
        request.state.system_code  = auth_context.system_code
        request.state.channel      = auth_context.channel

        await self.app(scope, receive, send)


    @staticmethod
    def _try_user_jwt(session: Session, token: str, client_type: str) -> Optional[AuthContext]:
        try:
            payload = decode_token(token, expected_type = "access")
            user_id = UUID(payload["sub"])
        except (jwt.PyJWTError, ValueError, KeyError):
            return None

        user = (
            session.query(USER_MODEL)
            .filter(
                USER_MODEL.id == user_id
                , USER_MODEL.is_active.is_(True)
                , USER_MODEL.status_code == STATUS_CODE_ENUM.ACTIVE.value
                , USER_MODEL.deleted_datetime.is_(None)
            )
            .first()
        )
        if not user or user.token_version != payload.get("ver"):
            return None

        session.expunge(user)
        system_code = "MSM_MOBILE" if client_type == "mobile" else "MSM_WEB"
        return AuthContext(
            system_code       = system_code
            , auth_type       = AUTH_TYPE_ENUM.JWT.value
            , channel         = CHANNEL_ENUM.API.value
            , user_id         = user.id
            , username        = user.username
            , role_code       = user.role_code
            , department_code = user.department_code
            , user            = user
        )


    @staticmethod
    def _resolve_auth(auth_type: str, auth_value: str, client_type: str) -> Optional[AuthContext]:
        if auth_type not in _SUPPORTED_AUTH_TYPES:
            return None

        session = getStaticSession()
        try:
            # 1. For Bearer tokens, try RS256 User JWT first
            if auth_type == AUTH_TYPE_ENUM.BEARER.value:
                jwt_context = AuthMiddleware._try_user_jwt(session, auth_value, client_type)
                if jwt_context is not None:
                    return jwt_context

            # 2. Fallback to M2M system credentials (API_KEY / BEARER / BASIC)
            row = _verify_system_credential(
                session      = session
                , auth_type  = auth_type
                , auth_value = auth_value
            )
            if not row:
                return None

            credential, system = row
            session.expunge(system)
            session.expunge(credential)
            return AuthContext(
                system_code  = system.code
                , auth_type  = auth_type
                , channel    = CHANNEL_ENUM.SYSTEM.value
                , system     = system
                , credential = credential
            )
        finally:
            session.close()


    @staticmethod
    def _extract_auth(request: Request) -> Tuple[Optional[str], Optional[str]]:
        api_key = request.headers.get("X-API-Key")
        if api_key:
            return AUTH_TYPE_ENUM.API_KEY.value, api_key.strip().strip("'\"")

        authorization = request.headers.get("Authorization", "")
        if authorization:
            parts = authorization.strip().strip("'\"").split(" ", 1)
            if len(parts) == 2:
                scheme = parts[0].lower()
                token  = parts[1].strip("'\"")
                if scheme == "bearer" and token:
                    return AUTH_TYPE_ENUM.BEARER.value, token
                if scheme == "basic" and token:
                    return AUTH_TYPE_ENUM.BASIC.value, token

        return None, None
