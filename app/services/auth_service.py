from datetime import datetime, timedelta, timezone
from typing   import Any, Dict, List, Optional, Tuple
from uuid     import UUID, uuid4

from fastapi        import HTTPException, status
from sqlalchemy.orm import Session

from app.core.config       import settings
from app.core.constants    import utc_now_naive
from app.core.enum         import STATUS_CODE_ENUM
from app.core.log          import logger
from app.core.rate_limiter import login_rate_limiter, register_rate_limiter
from app.core.security     import (
    create_access_token
    , generate_csrf_token
    , generate_opaque_refresh_token
    , hash_password
    , hash_token
    , needs_password_rehash
    , verify_password
)
from app.models.base_data_model import ROLE_MODEL
from app.models.data_model      import (
    REFRESH_TOKEN_MODEL
    , USER_MODEL
)
from app.models.track_model     import AUTH_AUDIT_LOG_MODEL
from app.schemas.auth_schema import (
    AccessTokenResponse
    , ChangePasswordRequest
    , DeviceInfo
    , LoginRequest
    , RegisterRequest
    , SessionResponse
)
from app.services.permission_service import PermissionService


def _utc_now_naive() -> datetime:
    """Return current UTC timestamp (naive, matching PostgreSQL timestamp without time zone)."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


class AuthService:

    @staticmethod
    def _audit(
        session         : Session
        , event_type    : str
        , event_status  : str
        , user_id       : Optional[UUID]           = None
        , username      : Optional[str]            = None
        , ip_address    : Optional[str]            = None
        , user_agent    : Optional[str]            = None
        , detail        : Optional[str]            = None
        , metadata_json : Optional[Dict[str, Any]] = None
    ) -> None:
        """Persist an authentication audit event to auth.auth_audit_log and application logs."""
        session.add(
            AUTH_AUDIT_LOG_MODEL(
                user_id         = user_id
                , username      = username
                , event_type    = event_type
                , event_status  = event_status
                , ip_address    = ip_address
                , user_agent    = user_agent
                , detail        = detail
                , metadata_json = metadata_json
                , created_by    = username
            )
        )
        log_line = (
            f"AuthAudit [{event_type}] status={event_status} "
            f"user={username or user_id} ip={ip_address} detail={detail or ''}"
        )
        if event_status == "ALERT":
            logger.error(log_line)
        elif event_status == "FAILED":
            logger.warn(log_line)
        else:
            logger.info(log_line)


    @staticmethod
    def _record_login(
        session          : Session
        , username       : str
        , login_status   : str
        , user_id        : Optional[UUID] = None
        , ip_address     : Optional[str]  = None
        , user_agent     : Optional[str]  = None
        , failure_reason : Optional[str]  = None
    ) -> None:
        AuthService._audit(
            session        = session
            , event_type   = "LOGIN_SUCCESS" if login_status == "SUCCESS" else "LOGIN_FAILED"
            , event_status = login_status
            , user_id      = user_id
            , username     = username
            , ip_address   = ip_address
            , user_agent   = user_agent
            , detail       = failure_reason
        )
        session.commit()


    @staticmethod
    def register(
        session      : Session
        , payload    : RegisterRequest
        , created_by : Optional[str] = None
        , ip_address : Optional[str] = None
    ) -> USER_MODEL:
        rate_keys = [f"reg:actor:{created_by or payload.username}"]
        if ip_address:
            rate_keys.append(f"reg:ip:{ip_address}")
        register_rate_limiter.enforce(rate_keys)
        for key in rate_keys:
            register_rate_limiter.record_attempt(key)

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
            , token_version   = 0
            , status_code     = STATUS_CODE_ENUM.ACTIVE.value
            , created_by      = created_by or payload.username
        )
        session.add(user)
        session.flush()
        AuthService._audit(
            session        = session
            , event_type   = "USER_REGISTERED"
            , event_status = "SUCCESS"
            , user_id      = user.id
            , username     = user.username
        )
        session.commit()
        session.refresh(user)
        return user


    @staticmethod
    def _issue_session_tokens(
        session      : Session
        , user       : USER_MODEL
        , is_mobile  : bool                 = False
        , family_id  : Optional[UUID]       = None
        , device     : Optional[DeviceInfo] = None
        , ip_address : Optional[str]        = None
        , user_agent : Optional[str]        = None
    ) -> Tuple[AccessTokenResponse, str, str]:
        """Issue RS256 access JWT + random opaque refresh token and persist only the SHA-256 hash.

        Returns (access_token_response, raw_opaque_refresh_token, new_jti).
        """
        now_utc            = _utc_now_naive()
        new_jti            = str(uuid4())
        session_family     = family_id or uuid4()
        csrf_token         = None if is_mobile else generate_csrf_token()
        raw_refresh_token  = generate_opaque_refresh_token()

        access_token = create_access_token(
            subject         = str(user.id)
            , token_version = user.token_version
            , extra_claims  = {
                "username"          : user.username
                , "role_code"       : user.role_code
                , "department_code" : user.department_code
            }
        )

        refresh_record = REFRESH_TOKEN_MODEL(
            user_id              = user.id
            , family_id          = session_family
            , jti                = new_jti
            , token_hash         = hash_token(raw_refresh_token)
            , device_id          = device.device_id   if device else None
            , device_name        = device.device_name if device else None
            , platform           = device.platform    if device else ("mobile" if is_mobile else "web")
            , ip_address         = ip_address
            , user_agent         = user_agent
            , expires_at         = now_utc + timedelta(days = settings.JWT_REFRESH_TOKEN_EXPIRE_DAYS)
            , last_used_datetime = now_utc
            , revoked            = False
            , created_by         = user.username
        )
        session.add(refresh_record)
        session.commit()

        response_body = AccessTokenResponse(
            access_token    = access_token
            , refresh_token = raw_refresh_token if is_mobile else None
            , token_type    = "bearer"
            , expires_in    = settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES * 60
            , csrf_token    = csrf_token
        )
        return response_body, raw_refresh_token, new_jti


    @classmethod
    def login(
        cls
        , session    : Session
        , payload    : LoginRequest
        , is_mobile  : bool          = False
        , ip_address : Optional[str] = None
        , user_agent : Optional[str] = None
    ) -> Tuple[AccessTokenResponse, str]:
        """Authenticate user with sliding-window rate limiting and Argon2id verification."""
        rate_keys = [f"user:{payload.username.lower()}"]
        if ip_address:
            rate_keys.append(f"ip:{ip_address}")

        try:
            login_rate_limiter.enforce(rate_keys)
        except HTTPException:
            cls._audit(
                session        = session
                , event_type   = "LOGIN_RATE_LIMITED"
                , event_status = "ALERT"
                , username     = payload.username
                , ip_address   = ip_address
                , user_agent   = user_agent
                , detail       = "Login rate limit exceeded."
            )
            session.commit()
            raise

        user = (
            session.query(USER_MODEL)
            .filter(
                USER_MODEL.username == payload.username
                , USER_MODEL.deleted_datetime.is_(None)
            )
            .first()
        )
        if not user or not verify_password(payload.password, user.password_hash):
            for key in rate_keys:
                login_rate_limiter.record_attempt(key)
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
            for key in rate_keys:
                login_rate_limiter.record_attempt(key)
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

        for key in rate_keys:
            login_rate_limiter.reset(key)

        if needs_password_rehash(user.password_hash):
            user.password_hash = hash_password(payload.password)

        user.last_login_datetime = _utc_now_naive()
        cls._record_login(
            session        = session
            , username     = user.username
            , login_status = "SUCCESS"
            , user_id      = user.id
            , ip_address   = ip_address
            , user_agent   = user_agent
        )
        token_response, raw_refresh_token, _ = cls._issue_session_tokens(
            session      = session
            , user       = user
            , is_mobile  = is_mobile
            , device     = payload.device
            , ip_address = ip_address
            , user_agent = user_agent
        )
        return token_response, raw_refresh_token


    @classmethod
    def _revoke_token_family(
        cls
        , session    : Session
        , family_id  : UUID
        , reason     : str
        , updated_by : Optional[str] = None
    ) -> int:
        now_utc = _utc_now_naive()
        rows    = (
            session.query(REFRESH_TOKEN_MODEL)
            .filter(
                REFRESH_TOKEN_MODEL.family_id == family_id
                , REFRESH_TOKEN_MODEL.revoked.is_(False)
            )
            .all()
        )
        for row in rows:
            row.revoked          = True
            row.revoked_datetime = now_utc
            row.revoke_reason    = reason
            row.updated_by       = updated_by
        return len(rows)


    @classmethod
    def _revoke_all_user_sessions(
        cls
        , session            : Session
        , user_id            : UUID
        , reason             : str
        , updated_by         : Optional[str] = None
        , exclude_token_hash : Optional[str] = None
    ) -> int:
        now_utc = _utc_now_naive()
        query   = session.query(REFRESH_TOKEN_MODEL).filter(
            REFRESH_TOKEN_MODEL.user_id == user_id
            , REFRESH_TOKEN_MODEL.revoked.is_(False)
        )
        if exclude_token_hash:
            query = query.filter(REFRESH_TOKEN_MODEL.token_hash != exclude_token_hash)

        rows = query.all()
        for row in rows:
            row.revoked          = True
            row.revoked_datetime = now_utc
            row.revoke_reason    = reason
            row.updated_by       = updated_by
        return len(rows)


    @classmethod
    def refresh(
        cls
        , session           : Session
        , refresh_token_str : Optional[str]
        , is_mobile         : bool          = False
        , ip_address        : Optional[str] = None
        , user_agent        : Optional[str] = None
    ) -> Tuple[AccessTokenResponse, str]:
        """Atomically lock (FOR UPDATE), detect reuse, and rotate an opaque refresh token."""
        if not refresh_token_str:
            raise HTTPException(
                status_code = status.HTTP_401_UNAUTHORIZED
                , detail    = "Missing refresh token."
            )

        token_digest = hash_token(refresh_token_str)
        rt           = (
            session.query(REFRESH_TOKEN_MODEL)
            .filter(REFRESH_TOKEN_MODEL.token_hash == token_digest)
            .with_for_update()
            .first()
        )
        now_utc = _utc_now_naive()

        if not rt:
            cls._audit(
                session        = session
                , event_type   = "TOKEN_REFRESH_UNKNOWN"
                , event_status = "FAILED"
                , ip_address   = ip_address
                , user_agent   = user_agent
                , detail       = "Submitted opaque refresh token was not found."
            )
            session.commit()
            raise HTTPException(
                status_code = status.HTTP_401_UNAUTHORIZED
                , detail    = "Invalid or expired refresh token."
            )

        # REUSE DETECTION: an already-revoked token was replayed -> revoke entire family!
        if rt.revoked:
            revoked_count = cls._revoke_token_family(
                session     = session
                , family_id = rt.family_id
                , reason    = "TOKEN_REUSE_DETECTED"
            )
            cls._audit(
                session         = session
                , event_type    = "TOKEN_REUSE_DETECTED"
                , event_status  = "ALERT"
                , user_id       = rt.user_id
                , ip_address    = ip_address
                , user_agent    = user_agent
                , detail        = f"Revoked refresh token replayed; invalidated family {rt.family_id} ({revoked_count} active token(s))."
                , metadata_json = {"family_id": str(rt.family_id), "replayed_jti": rt.jti}
            )
            session.commit()
            raise HTTPException(
                status_code = status.HTTP_401_UNAUTHORIZED
                , detail    = "Refresh token reuse detected. Session family has been revoked."
            )

        if rt.expires_at < now_utc:
            rt.revoked          = True
            rt.revoked_datetime = now_utc
            rt.revoke_reason    = "EXPIRED"
            session.commit()
            raise HTTPException(
                status_code = status.HTTP_401_UNAUTHORIZED
                , detail    = "Refresh token expired."
            )

        user = (
            session.query(USER_MODEL)
            .filter(
                USER_MODEL.id == rt.user_id
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

        # Rotate atomically within the same token family, preserving device metadata
        device_info = DeviceInfo(
            device_id     = rt.device_id
            , device_name = rt.device_name
            , platform    = rt.platform
        )
        rt.revoked            = True
        rt.revoked_datetime   = now_utc
        rt.revoke_reason      = "ROTATED"
        rt.last_used_datetime = now_utc

        token_response, new_refresh_token, new_jti = cls._issue_session_tokens(
            session      = session
            , user       = user
            , is_mobile  = is_mobile
            , family_id  = rt.family_id
            , device     = device_info
            , ip_address = ip_address
            , user_agent = user_agent
        )
        rt.replaced_by_jti = new_jti
        cls._audit(
            session         = session
            , event_type    = "TOKEN_REFRESH"
            , event_status  = "SUCCESS"
            , user_id       = user.id
            , username      = user.username
            , ip_address    = ip_address
            , user_agent    = user_agent
            , metadata_json = {"family_id": str(rt.family_id), "old_jti": rt.jti, "new_jti": new_jti}
        )
        session.commit()
        return token_response, new_refresh_token


    @classmethod
    def logout(
        cls
        , session           : Session
        , refresh_token_str : Optional[str]
        , ip_address        : Optional[str] = None
        , user_agent        : Optional[str] = None
    ) -> None:
        """Revoke the current opaque refresh session."""
        if not refresh_token_str:
            return

        token_digest = hash_token(refresh_token_str)
        rt           = (
            session.query(REFRESH_TOKEN_MODEL)
            .filter(REFRESH_TOKEN_MODEL.token_hash == token_digest)
            .first()
        )
        if rt and not rt.revoked:
            rt.revoked          = True
            rt.revoked_datetime = _utc_now_naive()
            rt.revoke_reason    = "LOGOUT"
            cls._audit(
                session        = session
                , event_type   = "LOGOUT"
                , event_status = "SUCCESS"
                , user_id      = rt.user_id
                , ip_address   = ip_address
                , user_agent   = user_agent
                , detail       = f"Revoked session {rt.id}"
            )
            session.commit()


    @classmethod
    def logout_all(
        cls
        , session      : Session
        , current_user : USER_MODEL
        , ip_address   : Optional[str] = None
        , user_agent   : Optional[str] = None
    ) -> int:
        """Revoke all active refresh sessions AND bump token_version for immediate JWT invalidation."""
        current_user.token_version    = (current_user.token_version or 0) + 1
        current_user.updated_by       = current_user.username
        current_user.updated_datetime = _utc_now_naive()

        revoked_count = cls._revoke_all_user_sessions(
            session      = session
            , user_id    = current_user.id
            , reason     = "LOGOUT_ALL"
            , updated_by = current_user.username
        )
        cls._audit(
            session        = session
            , event_type   = "LOGOUT_ALL"
            , event_status = "SUCCESS"
            , user_id      = current_user.id
            , username     = current_user.username
            , ip_address   = ip_address
            , user_agent   = user_agent
            , detail       = f"Revoked {revoked_count} active session(s); token_version={current_user.token_version}."
        )
        session.commit()
        return revoked_count


    @classmethod
    def revoke_session(
        cls
        , session      : Session
        , current_user : USER_MODEL
        , session_id   : UUID
        , ip_address   : Optional[str] = None
        , user_agent   : Optional[str] = None
    ) -> None:
        """Revoke a specific device session (resource-level check: owner or ADMIN only)."""
        rt = session.query(REFRESH_TOKEN_MODEL).filter(REFRESH_TOKEN_MODEL.id == session_id).first()
        if not rt:
            raise HTTPException(
                status_code = status.HTTP_404_NOT_FOUND
                , detail    = "Session not found."
            )

        PermissionService.enforce_owner_or_admin(
            current_user    = current_user
            , owner_user_id = rt.user_id
        )

        if not rt.revoked:
            rt.revoked          = True
            rt.revoked_datetime = _utc_now_naive()
            rt.revoke_reason    = "SESSION_REVOKED_BY_USER"
            rt.updated_by       = current_user.username
            cls._audit(
                session         = session
                , event_type    = "SESSION_REVOKED"
                , event_status  = "SUCCESS"
                , user_id       = current_user.id
                , username      = current_user.username
                , ip_address    = ip_address
                , user_agent    = user_agent
                , detail        = f"Revoked session {session_id}"
                , metadata_json = {"session_id": str(session_id), "device_id": rt.device_id}
            )
            session.commit()


    @classmethod
    def change_password(
        cls
        , session           : Session
        , current_user      : USER_MODEL
        , payload           : ChangePasswordRequest
        , refresh_token_str : Optional[str] = None
        , ip_address        : Optional[str] = None
        , user_agent        : Optional[str] = None
    ) -> None:
        """Verify current password, re-hash with Argon2id, bump token_version, and revoke other sessions."""
        if not verify_password(payload.current_password, current_user.password_hash):
            cls._audit(
                session        = session
                , event_type   = "PASSWORD_CHANGED"
                , event_status = "FAILED"
                , user_id      = current_user.id
                , username     = current_user.username
                , ip_address   = ip_address
                , user_agent   = user_agent
                , detail       = "Current password verification failed."
            )
            session.commit()
            raise HTTPException(
                status_code = status.HTTP_400_BAD_REQUEST
                , detail    = "Current password is incorrect."
            )

        if payload.current_password == payload.new_password:
            raise HTTPException(
                status_code = status.HTTP_400_BAD_REQUEST
                , detail    = "New password must be different from the current password."
            )

        current_hash                  = hash_token(refresh_token_str) if refresh_token_str else None
        current_user.password_hash    = hash_password(payload.new_password)
        current_user.token_version    = (current_user.token_version or 0) + 1
        current_user.updated_by       = current_user.username
        current_user.updated_datetime = _utc_now_naive()

        revoked_count = cls._revoke_all_user_sessions(
            session              = session
            , user_id            = current_user.id
            , reason             = "PASSWORD_CHANGED"
            , updated_by         = current_user.username
            , exclude_token_hash = current_hash
        )
        cls._audit(
            session        = session
            , event_type   = "PASSWORD_CHANGED"
            , event_status = "SUCCESS"
            , user_id      = current_user.id
            , username     = current_user.username
            , ip_address   = ip_address
            , user_agent   = user_agent
            , detail       = f"Password updated; revoked {revoked_count} other session(s); token_version={current_user.token_version}."
        )
        session.commit()


    @staticmethod
    def list_sessions(
        session             : Session
        , current_user      : USER_MODEL
        , refresh_token_str : Optional[str] = None
    ) -> List[SessionResponse]:
        """List active (non-revoked, non-expired) device sessions for the authenticated user."""
        current_hash = hash_token(refresh_token_str) if refresh_token_str else None
        now_utc      = _utc_now_naive()
        rows         = (
            session.query(REFRESH_TOKEN_MODEL)
            .filter(
                REFRESH_TOKEN_MODEL.user_id == current_user.id
                , REFRESH_TOKEN_MODEL.revoked.is_(False)
                , REFRESH_TOKEN_MODEL.expires_at > now_utc
            )
            .order_by(REFRESH_TOKEN_MODEL.created_datetime.desc())
            .all()
        )
        return [
            SessionResponse(
                id                   = row.id
                , family_id          = row.family_id
                , device_id          = row.device_id
                , device_name        = row.device_name
                , platform           = row.platform
                , ip_address         = row.ip_address
                , user_agent         = row.user_agent
                , created_datetime   = row.created_datetime
                , last_used_datetime = row.last_used_datetime
                , expires_at         = row.expires_at
                , is_current         = (row.token_hash == current_hash) if current_hash else False
            )
            for row in rows
        ]
