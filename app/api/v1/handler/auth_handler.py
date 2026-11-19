from typing import List, Optional
from uuid   import UUID

from fastapi        import APIRouter, Body, Depends, Request, Response
from sqlalchemy.orm import Session

from app.api.deps.auth_deps          import get_current_user, is_mobile_client, require_csrf_if_web
from app.core.config                 import settings
from app.core.db                     import getSession
from app.models.auth_model           import USER_MODEL
from app.schemas.auth_schema         import (
    AccessTokenResponse
    , ChangePasswordRequest
    , ForgotPasswordRequest
    , ForgotPasswordResponse
    , LoginRequest
    , RefreshTokenBody
    , RegisterRequest
    , ResetPasswordRequest
    , SessionResponse
    , UserResponse
)
from app.schemas.base_schema         import IResponseBase
from app.services.auth_service       import AuthService
from app.services.permission_service import PermissionService

router = APIRouter()


def _set_auth_cookies(
    response        : Response
    , refresh_token : str
    , csrf_token    : str
) -> None:
    """Set HttpOnly Secure SameSite refresh cookie + JS-readable double-submit CSRF cookie (web clients)."""
    max_age      = settings.JWT_REFRESH_TOKEN_EXPIRE_DAYS * 86400
    cookie_extra = {"domain": settings.COOKIE_DOMAIN} if settings.COOKIE_DOMAIN else {}

    response.set_cookie(
        key        = settings.COOKIE_REFRESH_NAME
        , value    = refresh_token
        , httponly = True
        , secure   = settings.COOKIE_SECURE
        , samesite = settings.COOKIE_SAMESITE
        , max_age  = max_age
        , path     = settings.COOKIE_REFRESH_PATH
        , **cookie_extra
    )
    response.set_cookie(
        key        = settings.COOKIE_CSRF_NAME
        , value    = csrf_token
        , httponly = False
        , secure   = settings.COOKIE_SECURE
        , samesite = settings.COOKIE_SAMESITE
        , max_age  = max_age
        , path     = "/"
        , **cookie_extra
    )


def _clear_auth_cookies(response: Response) -> None:
    cookie_extra = {"domain": settings.COOKIE_DOMAIN} if settings.COOKIE_DOMAIN else {}
    response.delete_cookie(
        key    = settings.COOKIE_REFRESH_NAME
        , path = settings.COOKIE_REFRESH_PATH
        , **cookie_extra
    )
    response.delete_cookie(
        key    = settings.COOKIE_CSRF_NAME
        , path = "/"
        , **cookie_extra
    )


def _extract_refresh_token(request: Request, body: Optional[RefreshTokenBody]) -> Optional[str]:
    """Read opaque refresh token from JSON body for mobile clients, or HttpOnly cookie for web clients."""
    if is_mobile_client(request):
        return body.refresh_token if body else None
    return request.cookies.get(settings.COOKIE_REFRESH_NAME)


@router.post(
    "/register"
    , response_model = IResponseBase[UserResponse]
    , summary        = "Register a new user"
)
def register(
    payload   : RegisterRequest
    , session : Session = Depends(getSession)
):
    user = AuthService.register(session, payload)
    return IResponseBase(
        data      = UserResponse.model_validate(user)
        , message = "User registered successfully"
    )


@router.post(
    "/login"
    , response_model = IResponseBase[AccessTokenResponse]
    , summary        = "Login (Web: HttpOnly cookie + CSRF; Mobile with X-Client-Type: mobile: opaque refresh_token in JSON)"
)
def login(
    payload    : LoginRequest
    , request  : Request
    , response : Response
    , session  : Session = Depends(getSession)
):
    mobile     = is_mobile_client(request)
    ip_address = request.client.host if request.client else None
    user_agent = request.headers.get("user-agent")
    token_data, raw_refresh_token = AuthService.login(
        session      = session
        , payload    = payload
        , is_mobile  = mobile
        , ip_address = ip_address
        , user_agent = user_agent
    )
    if not mobile and token_data.csrf_token:
        _set_auth_cookies(
            response        = response
            , refresh_token = raw_refresh_token
            , csrf_token    = token_data.csrf_token
        )
    return IResponseBase(
        data      = token_data
        , message = "Login successful"
    )


@router.post(
    "/refresh"
    , response_model = IResponseBase[AccessTokenResponse]
    , summary        = "Rotate opaque refresh token (cookie for web, JSON body for mobile) and issue a new RS256 access token"
    , dependencies   = [Depends(require_csrf_if_web)]
)
def refresh(
    request    : Request
    , response : Response
    , payload  : Optional[RefreshTokenBody] = Body(default = None)
    , session  : Session                    = Depends(getSession)
):
    mobile     = is_mobile_client(request)
    raw_token  = _extract_refresh_token(request, payload)
    ip_address = request.client.host if request.client else None
    user_agent = request.headers.get("user-agent")
    try:
        token_data, new_refresh_token = AuthService.refresh(
            session             = session
            , refresh_token_str = raw_token
            , is_mobile         = mobile
            , ip_address        = ip_address
            , user_agent        = user_agent
        )
    except Exception:
        if not mobile:
            _clear_auth_cookies(response)
        raise

    if not mobile and token_data.csrf_token:
        _set_auth_cookies(
            response        = response
            , refresh_token = new_refresh_token
            , csrf_token    = token_data.csrf_token
        )
    return IResponseBase(
        data      = token_data
        , message = "Token refreshed"
    )


@router.post(
    "/logout"
    , response_model = IResponseBase[None]
    , summary        = "Revoke current refresh session (cookie for web, JSON body for mobile)"
    , dependencies   = [Depends(require_csrf_if_web)]
)
def logout(
    request    : Request
    , response : Response
    , payload  : Optional[RefreshTokenBody] = Body(default = None)
    , session  : Session                    = Depends(getSession)
):
    mobile     = is_mobile_client(request)
    raw_token  = _extract_refresh_token(request, payload)
    ip_address = request.client.host if request.client else None
    user_agent = request.headers.get("user-agent")
    AuthService.logout(
        session             = session
        , refresh_token_str = raw_token
        , ip_address        = ip_address
        , user_agent        = user_agent
    )
    if not mobile:
        _clear_auth_cookies(response)
    return IResponseBase(message = "Logged out successfully")


@router.post(
    "/logout-all"
    , response_model = IResponseBase[dict]
    , summary        = "Revoke all active sessions and invalidate existing access tokens via token_version"
)
def logout_all(
    request        : Request
    , response     : Response
    , current_user : USER_MODEL = Depends(get_current_user)
    , session      : Session    = Depends(getSession)
):
    ip_address    = request.client.host if request.client else None
    user_agent    = request.headers.get("user-agent")
    revoked_count = AuthService.logout_all(
        session        = session
        , current_user = current_user
        , ip_address   = ip_address
        , user_agent   = user_agent
    )
    if not is_mobile_client(request):
        _clear_auth_cookies(response)
    return IResponseBase(
        data      = {"revoked_sessions": revoked_count}
        , message = "All sessions revoked successfully"
    )


@router.get(
    "/me"
    , response_model = IResponseBase[UserResponse]
    , summary        = "Get current authenticated user and effective RBAC permissions"
)
def me(
    current_user : USER_MODEL = Depends(get_current_user)
    , session    : Session    = Depends(getSession)
):
    user_data             = UserResponse.model_validate(current_user)
    user_data.permissions = PermissionService.get_effective_permissions_map(
        session     = session
        , role_code = current_user.role_code
    )
    return IResponseBase(data = user_data)


@router.post(
    "/change-password"
    , response_model = IResponseBase[None]
    , summary        = "Change password for the authenticated user"
)
def change_password(
    payload        : ChangePasswordRequest
    , request      : Request
    , current_user : USER_MODEL = Depends(get_current_user)
    , session      : Session    = Depends(getSession)
):
    raw_cookie = request.cookies.get(settings.COOKIE_REFRESH_NAME)
    ip_address = request.client.host if request.client else None
    user_agent = request.headers.get("user-agent")
    AuthService.change_password(
        session             = session
        , current_user      = current_user
        , payload           = payload
        , refresh_token_str = raw_cookie
        , ip_address        = ip_address
        , user_agent        = user_agent
    )
    return IResponseBase(message = "Password changed successfully")


@router.post(
    "/forgot-password"
    , response_model = IResponseBase[ForgotPasswordResponse]
    , summary        = "Request a password reset email (returns dev token/link in dev mode)"
)
def forgot_password(
    payload   : ForgotPasswordRequest
    , request : Request
    , session : Session = Depends(getSession)
):
    ip_address = request.client.host if request.client else None
    user_agent = request.headers.get("user-agent")
    result     = AuthService.forgot_password(
        session      = session
        , payload    = payload
        , ip_address = ip_address
        , user_agent = user_agent
    )
    return IResponseBase(
        data      = result
        , message = "If the account exists, a password reset link has been sent."
    )


@router.post(
    "/reset-password"
    , response_model = IResponseBase[None]
    , summary        = "Reset password using a single-use reset token"
)
def reset_password(
    payload   : ResetPasswordRequest
    , request : Request
    , session : Session = Depends(getSession)
):
    ip_address = request.client.host if request.client else None
    user_agent = request.headers.get("user-agent")
    AuthService.reset_password(
        session      = session
        , payload    = payload
        , ip_address = ip_address
        , user_agent = user_agent
    )
    return IResponseBase(message = "Password has been reset successfully")


@router.get(
    "/sessions"
    , response_model = IResponseBase[List[SessionResponse]]
    , summary        = "List active device sessions for the authenticated user"
)
def sessions(
    request        : Request
    , current_user : USER_MODEL = Depends(get_current_user)
    , session      : Session    = Depends(getSession)
):
    raw_cookie = request.cookies.get(settings.COOKIE_REFRESH_NAME)
    items      = AuthService.list_sessions(
        session             = session
        , current_user      = current_user
        , refresh_token_str = raw_cookie
    )
    return IResponseBase(data = items)


@router.delete(
    "/sessions/{session_id}"
    , response_model = IResponseBase[None]
    , summary        = "Revoke a specific device session (owner or ADMIN only)"
)
def revoke_session(
    session_id     : UUID
    , request      : Request
    , current_user : USER_MODEL = Depends(get_current_user)
    , session      : Session    = Depends(getSession)
):
    ip_address = request.client.host if request.client else None
    user_agent = request.headers.get("user-agent")
    AuthService.revoke_session(
        session        = session
        , current_user = current_user
        , session_id   = session_id
        , ip_address   = ip_address
        , user_agent   = user_agent
    )
    return IResponseBase(message = "Session revoked successfully")
