from datetime import datetime, timedelta, timezone
from typing   import Optional
from uuid     import uuid4

import jwt
from fastapi        import HTTPException, status
from sqlalchemy.orm import Session

from app.core.config   import settings
from app.core.enum     import STATUS_CODE_ENUM
from app.core.security import (
    create_access_token
    , create_refresh_token
    , decode_token
    , hash_password
    , verify_password
)
from app.models.auth_model import (
    LOGIN_HISTORY_MODEL
    , REFRESH_TOKEN_MODEL
    , ROLE_MODEL
    , USER_MODEL
)
from app.schemas.auth_schema import LoginRequest, RegisterRequest, TokenResponse


class AuthService:

    @staticmethod
    def register(session: Session, payload: RegisterRequest) -> USER_MODEL:
        existing = (
            session.query(USER_MODEL)
            .filter(USER_MODEL.username == payload.username)
            .first()
        )
        if existing:
            raise HTTPException(
                status_code = status.HTTP_409_CONFLICT
                , detail    = "Username already exists."
            )

        role = (
            session.query(ROLE_MODEL)
            .filter(ROLE_MODEL.code == payload.role_code)
            .first()
        )
        if not role:
            raise HTTPException(
                status_code = status.HTTP_400_BAD_REQUEST
                , detail    = f"Invalid role_code: {payload.role_code}"
            )

        user = USER_MODEL(
            username          = payload.username
            , email           = payload.email
            , full_name       = payload.full_name
            , full_name_kh    = payload.full_name_kh
            , password_hash   = hash_password(payload.password)
            , role_code       = payload.role_code
            , department_code = payload.department_code
            , is_active       = True
            , status_code     = STATUS_CODE_ENUM.ACTIVE.value
            , created_by      = payload.username
        )
        session.add(user)
        session.commit()
        session.refresh(user)
        return user


    @staticmethod
    def _issue_tokens(session: Session, user: USER_MODEL) -> TokenResponse:
        jti          = str(uuid4())
        access_token = create_access_token(
            subject        = str(user.id)
            , extra_claims = {
                "username"          : user.username
                , "role_code"       : user.role_code
                , "department_code" : user.department_code
            }
        )
        refresh_token = create_refresh_token(subject = str(user.id), jti = jti)

        rt = REFRESH_TOKEN_MODEL(
            user_id      = user.id
            , jti        = jti
            , expires_at = datetime.utcnow() + timedelta(days = settings.JWT_REFRESH_TOKEN_EXPIRE_DAYS)
            , revoked    = False
        )
        session.add(rt)
        session.commit()

        return TokenResponse(
            access_token    = access_token
            , refresh_token = refresh_token
            , expires_in    = settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES * 60
        )


    @staticmethod
    def _record_login(
        session           : Session
        , username        : str
        , login_status    : str
        , user_id         = None
        , ip_address      : Optional[str] = None
        , user_agent      : Optional[str] = None
        , failure_reason  : Optional[str] = None
    ) -> None:
        session.add(
            LOGIN_HISTORY_MODEL(
                user_id          = user_id
                , username       = username
                , ip_address     = ip_address
                , user_agent     = user_agent
                , login_status   = login_status
                , failure_reason = failure_reason
            )
        )
        session.commit()


    @classmethod
    def login(
        cls
        , session    : Session
        , payload    : LoginRequest
        , ip_address : Optional[str] = None
        , user_agent : Optional[str] = None
    ) -> TokenResponse:
        user = (
            session.query(USER_MODEL)
            .filter(
                USER_MODEL.username == payload.username
                , USER_MODEL.deleted_datetime.is_(None)
            )
            .first()
        )
        if not user or not verify_password(payload.password, user.password_hash):
            cls._record_login(
                session          = session
                , username       = payload.username
                , login_status   = "FAILED"
                , user_id        = user.id if user else None
                , ip_address     = ip_address
                , user_agent     = user_agent
                , failure_reason = "Invalid username or password"
            )
            raise HTTPException(
                status_code = status.HTTP_401_UNAUTHORIZED
                , detail    = "Invalid username or password."
            )
        if not user.is_active or user.status_code != STATUS_CODE_ENUM.ACTIVE.value:
            cls._record_login(
                session          = session
                , username       = payload.username
                , login_status   = "FAILED"
                , user_id        = user.id
                , ip_address     = ip_address
                , user_agent     = user_agent
                , failure_reason = "User account is inactive"
            )
            raise HTTPException(
                status_code = status.HTTP_403_FORBIDDEN
                , detail    = "User account is inactive."
            )

        user.last_login_datetime = datetime.now(timezone.utc).replace(tzinfo = None)
        cls._record_login(
            session        = session
            , username     = user.username
            , login_status = "SUCCESS"
            , user_id      = user.id
            , ip_address   = ip_address
            , user_agent   = user_agent
        )
        return cls._issue_tokens(session, user)


    @classmethod
    def refresh(cls, session: Session, refresh_token_str: str) -> TokenResponse:
        try:
            payload = decode_token(refresh_token_str)
        except jwt.PyJWTError:
            raise HTTPException(
                status_code = status.HTTP_401_UNAUTHORIZED
                , detail    = "Invalid or expired refresh token."
            )

        if payload.get("type") != "refresh":
            raise HTTPException(
                status_code = status.HTTP_401_UNAUTHORIZED
                , detail    = "Invalid token type."
            )

        jti = payload.get("jti")
        rt  = (
            session.query(REFRESH_TOKEN_MODEL)
            .filter(
                REFRESH_TOKEN_MODEL.jti == jti
                , REFRESH_TOKEN_MODEL.revoked.is_(False)
            )
            .first()
        )
        if not rt or rt.expires_at < datetime.utcnow():
            raise HTTPException(
                status_code = status.HTTP_401_UNAUTHORIZED
                , detail    = "Refresh token revoked or expired."
            )

        user = (
            session.query(USER_MODEL)
            .filter(
                USER_MODEL.id == rt.user_id
                , USER_MODEL.is_active.is_(True)
            )
            .first()
        )
        if not user:
            raise HTTPException(
                status_code = status.HTTP_401_UNAUTHORIZED
                , detail    = "User not found or inactive."
            )

        rt.revoked = True
        return cls._issue_tokens(session, user)
