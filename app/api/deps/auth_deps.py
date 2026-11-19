from typing import List
from uuid   import UUID

import jwt
from fastapi          import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm   import Session

from app.core.db                     import getSession
from app.core.enum                   import PERMISSION_ACTION_ENUM, STATUS_CODE_ENUM
from app.core.security               import decode_token
from app.models.auth_model           import USER_MODEL
from app.services.permission_service import PermissionService

bearer_scheme = HTTPBearer(auto_error = True)


def get_current_user(
    credentials : HTTPAuthorizationCredentials = Depends(bearer_scheme)
    , session   : Session = Depends(getSession)
) -> USER_MODEL:
    token = credentials.credentials
    try:
        payload = decode_token(token)
    except jwt.PyJWTError:
        raise HTTPException(
            status_code = status.HTTP_401_UNAUTHORIZED
            , detail    = "Invalid or expired access token."
        )

    if payload.get("type") != "access":
        raise HTTPException(
            status_code = status.HTTP_401_UNAUTHORIZED
            , detail    = "Invalid token type."
        )

    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(
            status_code = status.HTTP_401_UNAUTHORIZED
            , detail    = "Invalid token subject."
        )

    user = (
        session.query(USER_MODEL)
        .filter(
            USER_MODEL.id == UUID(user_id)
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
    return user


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
