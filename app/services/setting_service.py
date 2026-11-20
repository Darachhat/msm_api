from typing   import List, Optional
from uuid     import UUID

from fastapi        import HTTPException, status
from sqlalchemy.orm import Session

from app.core.constants         import utc_now_naive
from app.core.enum              import STATUS_CODE_ENUM
from app.core.log               import logger
from app.core.security          import hash_password
from app.models.auth_model      import LOGIN_HISTORY_MODEL, REFRESH_TOKEN_MODEL, ROLE_MODEL, USER_MODEL
from app.schemas.setting_schema import (
    RoleCreate
    , RolePermissionResponse
    , RoleResponse
    , UserCreateByAdmin
    , UserUpdateByAdmin
)
from app.services.permission_service import PermissionService


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
    def list_roles(session: Session) -> List[RoleResponse]:
        roles = (
            session.query(ROLE_MODEL)
            .filter(ROLE_MODEL.deleted_datetime.is_(None))
            .order_by(ROLE_MODEL.code)
            .all()
        )
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
                    , permissions = [RolePermissionResponse.model_validate(p) for p in perms]
                )
            )
        return out


    @staticmethod
    def create_role(session: Session, payload: RoleCreate, actor: str) -> RoleResponse:
        existing = session.query(ROLE_MODEL).filter(ROLE_MODEL.code == payload.code).first()
        if existing:
            logger.warn(
                "SettingService.create_role: duplicate role code"
                , f"code: {payload.code}"
                , f"actor: {actor}"
            )
            raise HTTPException(
                status_code = status.HTTP_409_CONFLICT
                , detail    = "Role code already exists."
            )

        role = ROLE_MODEL(
            code          = payload.code.upper()
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
            , permissions = [RolePermissionResponse.model_validate(p) for p in perms]
        )


    @staticmethod
    def list_login_history(
        session        : Session
        , username     : Optional[str] = None
        , login_status : Optional[str] = None
        , limit        : int = 100
    ) -> List[LOGIN_HISTORY_MODEL]:
        query = session.query(LOGIN_HISTORY_MODEL)
        if username:
            query = query.filter(LOGIN_HISTORY_MODEL.username.ilike(f"%{username}%"))
        if login_status:
            query = query.filter(LOGIN_HISTORY_MODEL.login_status == login_status)
        return query.order_by(LOGIN_HISTORY_MODEL.login_datetime.desc()).limit(limit).all()
