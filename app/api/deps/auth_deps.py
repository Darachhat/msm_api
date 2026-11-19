from typing import List, Optional
from uuid   import UUID

import jwt
from fastapi          import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm   import Session

from app.core.config                 import settings
from app.core.db                     import getSession
from app.core.enum                   import PERMISSION_ACTION_ENUM, STATUS_CODE_ENUM
from app.core.security               import decode_token, verify_csrf_token
from app.models.auth_model           import USER_MODEL
from app.services.permission_service import PermissionService

bearer_scheme = HTTPBearer(auto_error = True)


def get_current_user(
    credentials : HTTPAuthorizationCredentials = Depends(bearer_scheme)
    , session   : Session = Depends(getSession)
) -> USER_MODEL:
    token = credentials.credentials
    try:
        payload = decode_token(token, expected_type = "access")
    except jwt.PyJWTError:
        raise HTTPException(
            status_code = status.HTTP_401_UNAUTHORIZED
            , detail    = "Invalid or expired access token."
        )

    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(
            status_code = status.HTTP_401_UNAUTHORIZED
            , detail    = "Invalid token subject."
        )

    try:
        parsed_user_id = UUID(user_id)
    except ValueError:
        raise HTTPException(
            status_code = status.HTTP_401_UNAUTHORIZED
            , detail    = "Malformed token subject."
        )

    user = (
        session.query(USER_MODEL)
        .filter(
            USER_MODEL.id == parsed_user_id
            , USER_MODEL.is_active.is_(True)
            , USER_MODEL.status_code == STATUS_CODE_ENUM.ACTIVE.value
            , USER_MODEL.deleted_datetime.is_(None)
        )
        .first()
    )
    if not user:
        raise HTTPException(
            status_code = status.HTTP_401_UNAUTHORIZED
            , detail    = "User not found or inactive."
        )
    if user.token_version != payload.get("ver"):
        raise HTTPException(
            status_code = status.HTTP_401_UNAUTHORIZED
            , detail    = "Token has been revoked."
        )
    return user


def is_mobile_client(request: Request) -> bool:
    return (request.headers.get("X-Client-Type") or "").strip().lower() == "mobile"


def require_csrf_if_web(request: Request) -> None:
    """Double-submit CSRF protection for cookie-authenticated web clients.
    Mobile clients (X-Client-Type: mobile) authenticate refresh/logout via JSON body, not cookies."""
    if is_mobile_client(request):
        return
    cookie_token = request.cookies.get(settings.COOKIE_CSRF_NAME)
    header_token = request.headers.get("X-CSRF-Token")
    if not verify_csrf_token(cookie_token, header_token):
        raise HTTPException(
            status_code = status.HTTP_403_FORBIDDEN
            , detail    = "Invalid or missing CSRF token."
        )


def require_roles(allowed_roles: List[str]):
    def _checker(current_user: USER_MODEL = Depends(get_current_user)) -> USER_MODEL:
        if current_user.role_code not in allowed_roles:
            raise HTTPException(
                status_code = status.HTTP_403_FORBIDDEN
                , detail    = "Insufficient permissions."
            )
        return current_user

    return _checker


def require_permission(service_code: str, action: PERMISSION_ACTION_ENUM):
    def _checker(
        current_user : USER_MODEL = Depends(get_current_user)
        , session    : Session = Depends(getSession)
    ) -> USER_MODEL:
        if not PermissionService.has_permission(
            session        = session
            , role_code    = current_user.role_code
            , service_code = service_code
            , action       = action
        ):
            raise HTTPException(
                status_code = status.HTTP_403_FORBIDDEN
                , detail    = f"Permission denied: {action.value} on {service_code}."
            )
        return current_user

    return _checker


def require_resource_permission(
    service_code       : str
    , action           : PERMISSION_ACTION_ENUM
    , department_param : Optional[str] = "department_code"
):
    """Combined RBAC (role/module/action) + resource-level department scope dependency."""
    def _checker(
        request        : Request
        , current_user : USER_MODEL = Depends(require_permission(service_code, action))
    ) -> USER_MODEL:
        if department_param:
            target_dept = (
                request.path_params.get(department_param)
                or request.query_params.get(department_param)
            )
            PermissionService.enforce_department_scope(
                current_user             = current_user
                , target_department_code = target_dept
            )
        return current_user

    return _checker
