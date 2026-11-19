from fastapi        import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.api.deps.auth_deps    import get_current_user
from app.core.db               import getSession
from app.models.auth_model     import USER_MODEL
from app.schemas.auth_schema   import (
    LoginRequest
    , RefreshTokenRequest
    , RegisterRequest
    , TokenResponse
    , UserResponse
)
from app.schemas.base_schema   import IResponseBase
from app.services.auth_service import AuthService

router = APIRouter()


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
    , response_model = IResponseBase[TokenResponse]
    , summary        = "Login and obtain JWT tokens"
)
def login(
    payload   : LoginRequest
    , request : Request
    , session : Session = Depends(getSession)
):
    ip_address = request.client.host if request.client else None
    user_agent = request.headers.get("user-agent")
    tokens     = AuthService.login(
        session      = session
        , payload    = payload
        , ip_address = ip_address
        , user_agent = user_agent
    )
    return IResponseBase(
        data      = tokens
        , message = "Login successful"
    )


@router.post(
    "/refresh"
    , response_model = IResponseBase[TokenResponse]
    , summary        = "Refresh JWT access token"
)
def refresh(
    payload   : RefreshTokenRequest
    , session : Session = Depends(getSession)
):
    tokens = AuthService.refresh(session, payload.refresh_token)
    return IResponseBase(
        data      = tokens
        , message = "Token refreshed"
    )


@router.get(
    "/me"
    , response_model = IResponseBase[UserResponse]
    , summary        = "Get current authenticated user"
)
def me(
    current_user: USER_MODEL = Depends(get_current_user)
):
    return IResponseBase(data = UserResponse.model_validate(current_user))
