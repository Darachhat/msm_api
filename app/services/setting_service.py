from datetime import date, datetime, time
import re
from typing   import Dict, List, Optional, Tuple
from uuid     import UUID, uuid4

from fastapi        import HTTPException, status
from sqlalchemy     import func
from sqlalchemy.orm import Session

from app.core.constants         import utc_now_naive
from app.core.enum              import ROLE_CODE_ENUM, STATUS_CODE_ENUM
from app.core.log               import logger
from app.core.security          import hash_password
from app.models.base_data_model import ROLE_MODEL
from app.models.data_model      import REFRESH_TOKEN_MODEL, USER_MODEL
from app.models.track_model     import AUTH_AUDIT_LOG_MODEL
from app.schemas.setting_schema import (
    LoginHistoryResponse
    , RoleCreate
    , RolePermissionResponse
    , RoleResponse
    , RoleUpdate
    , UserCreateByAdmin
    , UserUpdateByAdmin
)
from app.services.permission_service import PermissionService


def _generate_role_code(name: str) -> str:
    slug = re.sub(r"[^A-Z0-9]+", "_", name.upper()).strip("_")[:40]
    if len(slug) < 2:
        slug = f"ROLE_{uuid4().hex[:6].upper()}"
    return slug


class SettingService:
    """Manages Users, Roles, Permissions, and Login History for the Setting tab."""

    @staticmethod
    def list_users(
        session  : Session
        , search : Optional[str] = None
        , limit  : int           = 100
        , offset : int           = 0
    ) -> List[USER_MODEL]:
        query = session.query(USER_MODEL).filter(USER_MODEL.deleted_datetime.is_(None))
        if search:
            query = query.filter(
                (USER_MODEL.username.ilike(f"%{search}%"))
                | (USER_MODEL.full_name.ilike(f"%{search}%"))
            )
        return query.order_by(USER_MODEL.created_datetime.desc()).offset(offset).limit(limit).all()


    @staticmethod
    def create_user(session: Session, payload: UserCreateByAdmin, actor: str) -> USER_MODEL:
        existing = session.query(USER_MODEL).filter(USER_MODEL.username == payload.username).first()
        if existing:
            logger.warn(
                "SettingService.create_user: duplicate username"
                , f"username: {payload.username}"
                , f"actor: {actor}"
            )
            raise HTTPException(
                status_code = status.HTTP_409_CONFLICT
                , detail    = "Username already exists."
            )

        role = session.query(ROLE_MODEL).filter(ROLE_MODEL.code == payload.role_code).first()
        if not role:
            logger.warn(
                "SettingService.create_user: invalid role_code"
                , f"role_code: {payload.role_code}"
                , f"actor: {actor}"
            )
            raise HTTPException(
                status_code = status.HTTP_400_BAD_REQUEST
                , detail    = "Invalid role_code."
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
            , created_by      = actor
        )
        session.add(user)
        session.commit()
        session.refresh(user)
        logger.info(
            "SettingService.create_user: created"
            , f"user_id: {user.id}"
            , f"username: {user.username}"
            , f"role_code: {user.role_code}"
            , f"actor: {actor}"
        )
        return user


    @staticmethod
    def update_user(
        session     : Session
        , user_id   : UUID
        , payload   : UserUpdateByAdmin
        , actor     : str
    ) -> USER_MODEL:
        user = (
            session.query(USER_MODEL)
            .filter(
                USER_MODEL.id == user_id
                , USER_MODEL.deleted_datetime.is_(None)
            )
            .first()
        )
        if not user:
            logger.warn(
                "SettingService.update_user: user not found"
                , f"user_id: {user_id}"
                , f"actor: {actor}"
            )
            raise HTTPException(
                status_code = status.HTTP_404_NOT_FOUND
                , detail    = "User not found."
            )

        data                 = payload.model_dump(exclude_unset = True)
        must_revoke_sessions = False
        if "password" in data:
            pw = data.pop("password")
            if pw:
                user.password_hash   = hash_password(pw)
                must_revoke_sessions = True
        if data.get("is_active") is False:
            must_revoke_sessions = True
        for k, v in data.items():
            setattr(user, k, v)

        now_utc               = utc_now_naive()
        user.updated_by       = actor
        user.updated_datetime = now_utc

        if must_revoke_sessions:
            user.token_version = (user.token_version or 0) + 1
            session.query(REFRESH_TOKEN_MODEL).filter(
                REFRESH_TOKEN_MODEL.user_id == user.id
                , REFRESH_TOKEN_MODEL.revoked.is_(False)
            ).update({
                "revoked"            : True
                , "revoked_datetime" : now_utc
                , "revoke_reason"    : "ADMIN_USER_UPDATED"
                , "updated_by"       : actor
            })

        session.commit()
        session.refresh(user)
        logger.info(
            "SettingService.update_user: updated"
            , f"user_id: {user_id}"
            , f"revoked_sessions: {must_revoke_sessions}"
            , f"actor: {actor}"
        )
        return user


    @staticmethod
    def delete_user(session: Session, user_id: UUID, actor: str) -> None:
        user = (
            session.query(USER_MODEL)
            .filter(
                USER_MODEL.id == user_id
                , USER_MODEL.deleted_datetime.is_(None)
            )
            .first()
        )
        if not user:
            logger.warn(
                "SettingService.delete_user: user not found"
                , f"user_id: {user_id}"
                , f"actor: {actor}"
            )
            raise HTTPException(
                status_code = status.HTTP_404_NOT_FOUND
                , detail    = "User not found."
            )
        now_utc               = utc_now_naive()
        user.is_active        = False
        user.token_version    = (user.token_version or 0) + 1
        user.status_code      = STATUS_CODE_ENUM.DELETED.value
        user.deleted_by       = actor
        user.deleted_datetime = now_utc
        session.query(REFRESH_TOKEN_MODEL).filter(
            REFRESH_TOKEN_MODEL.user_id == user.id
            , REFRESH_TOKEN_MODEL.revoked.is_(False)
        ).update({
            "revoked"            : True
            , "revoked_datetime" : now_utc
            , "revoke_reason"    : "ADMIN_USER_DELETED"
            , "updated_by"       : actor
        })
        session.commit()
        logger.info(
            "SettingService.delete_user: soft-deleted and sessions revoked"
            , f"user_id: {user_id}"
            , f"actor: {actor}"
        )


    @staticmethod
    def _role_user_counts(session: Session) -> Dict[str, int]:
        rows = (
            session.query(USER_MODEL.role_code, func.count(USER_MODEL.id))
            .filter(USER_MODEL.deleted_datetime.is_(None))
            .group_by(USER_MODEL.role_code)
            .all()
        )
        return {code: cnt for code, cnt in rows}


    @classmethod
    def list_roles(cls, session: Session) -> List[RoleResponse]:
        roles = (
            session.query(ROLE_MODEL)
            .filter(ROLE_MODEL.deleted_datetime.is_(None))
            .order_by(ROLE_MODEL.code)
            .all()
        )
        counts = cls._role_user_counts(session)
        out: List[RoleResponse] = []
        for r in roles:
            perms = PermissionService.get_role_permissions(session, r.code)
            out.append(
                RoleResponse(
                    id            = r.id
                    , code        = r.code
                    , name        = r.name
                    , description = r.description
                    , status_code = r.status_code
                    , user_count  = counts.get(r.code, 0)
                    , permissions = [RolePermissionResponse.model_validate(p) for p in perms]
                )
            )
        return out


    @classmethod
    def create_role(cls, session: Session, payload: RoleCreate, actor: str) -> RoleResponse:
        code = (payload.code or "").strip().upper() or _generate_role_code(payload.name)
        existing = session.query(ROLE_MODEL).filter(ROLE_MODEL.code == code).first()
        if existing:
            if payload.code:
                logger.warn(
                    "SettingService.create_role: duplicate role code"
                    , f"code: {code}"
                    , f"actor: {actor}"
                )
                raise HTTPException(
                    status_code = status.HTTP_409_CONFLICT
                    , detail    = "Role code already exists."
                )
            code = f"{code[:42]}_{uuid4().hex[:6].upper()}"

        role = ROLE_MODEL(
            code          = code
            , name        = payload.name
            , description = payload.description
            , created_by  = actor
        )
        session.add(role)
        session.commit()
        session.refresh(role)
        logger.info(
            "SettingService.create_role: created"
            , f"role_id: {role.id}"
            , f"code: {role.code}"
            , f"actor: {actor}"
        )

        perms = PermissionService.set_role_permissions(
            session       = session
            , role_code   = role.code
            , permissions = payload.permissions
            , username    = actor
        )
        return RoleResponse(
            id            = role.id
            , code        = role.code
            , name        = role.name
            , description = role.description
            , status_code = role.status_code
            , user_count  = 0
            , permissions = [RolePermissionResponse.model_validate(p) for p in perms]
        )


    @classmethod
    def update_role(
        cls
        , session   : Session
        , role_code : str
        , payload   : RoleUpdate
        , actor     : str
    ) -> RoleResponse:
        role = (
            session.query(ROLE_MODEL)
            .filter(
                ROLE_MODEL.code == role_code
                , ROLE_MODEL.deleted_datetime.is_(None)
            )
            .first()
        )
        if not role:
            raise HTTPException(
                status_code = status.HTTP_404_NOT_FOUND
                , detail    = f"Role '{role_code}' not found."
            )
        if role.code == ROLE_CODE_ENUM.ADMIN.value:
            raise HTTPException(
                status_code = status.HTTP_400_BAD_REQUEST
                , detail    = "System ADMIN role cannot be modified."
            )

        updates = payload.model_dump(exclude_unset = True, exclude = {"permissions"})
        for k, v in updates.items():
            setattr(role, k, v)
        role.updated_by       = actor
        role.updated_datetime = utc_now_naive()
        session.commit()
        session.refresh(role)

        if payload.permissions is not None:
            perms = PermissionService.set_role_permissions(
                session       = session
                , role_code   = role.code
                , permissions = payload.permissions
                , username    = actor
            )
        else:
            perms = PermissionService.get_role_permissions(session, role.code)

        counts = cls._role_user_counts(session)
        return RoleResponse(
            id            = role.id
            , code        = role.code
            , name        = role.name
            , description = role.description
            , status_code = role.status_code
            , user_count  = counts.get(role.code, 0)
            , permissions = [RolePermissionResponse.model_validate(p) for p in perms]
        )


    @classmethod
    def delete_role(cls, session: Session, role_code: str, actor: str) -> None:
        role = (
            session.query(ROLE_MODEL)
            .filter(
                ROLE_MODEL.code == role_code
                , ROLE_MODEL.deleted_datetime.is_(None)
            )
            .first()
        )
        if not role:
            raise HTTPException(
                status_code = status.HTTP_404_NOT_FOUND
                , detail    = f"Role '{role_code}' not found."
            )
        if role.code == ROLE_CODE_ENUM.ADMIN.value:
            raise HTTPException(
                status_code = status.HTTP_400_BAD_REQUEST
                , detail    = "System ADMIN role cannot be deleted."
            )

        assigned = (
            session.query(USER_MODEL.id)
            .filter(
                USER_MODEL.role_code == role.code
                , USER_MODEL.deleted_datetime.is_(None)
            )
            .count()
        )
        if assigned > 0:
            raise HTTPException(
                status_code = status.HTTP_400_BAD_REQUEST
                , detail    = f"Cannot delete role '{role.code}' because {assigned} user(s) are assigned to it."
            )

        role.status_code      = STATUS_CODE_ENUM.DELETED.value
        role.deleted_by       = actor
        role.deleted_datetime = utc_now_naive()
        session.commit()
        logger.info(
            "SettingService.delete_role: soft-deleted"
            , f"role_code: {role_code}"
            , f"actor: {actor}"
        )


    @staticmethod
    def list_login_history(
        session        : Session
        , username     : Optional[str]  = None
        , user_id      : Optional[UUID] = None
        , login_status : Optional[str]  = None
        , start_date   : Optional[date] = None
        , end_date     : Optional[date] = None
        , limit        : int            = 100
        , offset       : int            = 0
    ) -> Tuple[List[LoginHistoryResponse], int]:
        query = session.query(AUTH_AUDIT_LOG_MODEL).filter(
            AUTH_AUDIT_LOG_MODEL.event_type.in_(["LOGIN_SUCCESS", "LOGIN_FAILED"])
        )
        if username:
            query = query.filter(AUTH_AUDIT_LOG_MODEL.username.ilike(f"%{username}%"))
        if user_id:
            query = query.filter(AUTH_AUDIT_LOG_MODEL.user_id == user_id)
        if login_status:
            query = query.filter(AUTH_AUDIT_LOG_MODEL.event_status == login_status)
        if start_date:
            query = query.filter(AUTH_AUDIT_LOG_MODEL.created_datetime >= datetime.combine(start_date, time.min))
        if end_date:
            query = query.filter(AUTH_AUDIT_LOG_MODEL.created_datetime <= datetime.combine(end_date, time.max))

        total = query.count()
        rows  = (
            query.order_by(AUTH_AUDIT_LOG_MODEL.created_datetime.desc())
            .offset(offset)
            .limit(limit)
            .all()
        )
        items = [
            LoginHistoryResponse(
                id               = row.id
                , user_id        = row.user_id
                , username       = row.username or ""
                , ip_address     = row.ip_address
                , user_agent     = row.user_agent
                , login_status   = row.event_status
                , failure_reason = row.detail
                , login_datetime = row.created_datetime
            )
            for row in rows
        ]
        return items, total
