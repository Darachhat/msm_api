from datetime import datetime, timezone
from typing   import Dict, List, Optional
from uuid     import UUID

from fastapi        import HTTPException, status
from sqlalchemy.orm import Session

from app.core.enum              import PERMISSION_ACTION_ENUM, ROLE_CODE_ENUM, STATUS_CODE_ENUM
from app.core.log               import logger
from app.models.auth_model      import ROLE_MODEL, ROLE_PERMISSION_MODEL, SERVICE_MODULE_MODEL, USER_MODEL
from app.schemas.setting_schema import RolePermissionInput


class PermissionService:
    """RBAC + Resource-Level Permission service managing per-role module CRUD and resource ownership/department scoping."""

    @staticmethod
    def list_services(session: Session) -> List[SERVICE_MODULE_MODEL]:
        return (
            session.query(SERVICE_MODULE_MODEL)
            .filter(
                SERVICE_MODULE_MODEL.status_code == STATUS_CODE_ENUM.ACTIVE.value
                , SERVICE_MODULE_MODEL.deleted_datetime.is_(None)
            )
            .order_by(SERVICE_MODULE_MODEL.sort_order)
            .all()
        )


    @staticmethod
    def get_role_permissions(session: Session, role_code: str) -> List[ROLE_PERMISSION_MODEL]:
        return (
            session.query(ROLE_PERMISSION_MODEL)
            .filter(
                ROLE_PERMISSION_MODEL.role_code == role_code
                , ROLE_PERMISSION_MODEL.status_code == STATUS_CODE_ENUM.ACTIVE.value
                , ROLE_PERMISSION_MODEL.deleted_datetime.is_(None)
            )
            .all()
        )


    @classmethod
    def get_effective_permissions_map(cls, session: Session, role_code: str) -> Dict[str, List[str]]:
        """Return a mapping of service_code -> list of allowed action names for a role."""
        if role_code == ROLE_CODE_ENUM.ADMIN.value:
            all_actions = [action.value for action in PERMISSION_ACTION_ENUM]
            return {service.code: list(all_actions) for service in cls.list_services(session)}

        result: Dict[str, List[str]] = {}
        for perm in cls.get_role_permissions(session, role_code):
            actions: List[str] = []
            if perm.can_read:
                actions.append(PERMISSION_ACTION_ENUM.READ.value)
            if perm.can_write:
                actions.append(PERMISSION_ACTION_ENUM.WRITE.value)
            if perm.can_update:
                actions.append(PERMISSION_ACTION_ENUM.UPDATE.value)
            if perm.can_delete:
                actions.append(PERMISSION_ACTION_ENUM.DELETE.value)
            result[perm.service_code] = actions
        return result


    @classmethod
    def set_role_permissions(
        cls
        , session     : Session
        , role_code   : str
        , permissions : List[RolePermissionInput]
        , username    : str
    ) -> List[ROLE_PERMISSION_MODEL]:
        role = session.query(ROLE_MODEL).filter(ROLE_MODEL.code == role_code).first()
        if not role:
            logger.warn(
                "PermissionService.set_role_permissions: role not found"
                , f"role_code: {role_code}"
                , f"username: {username}"
            )
            raise HTTPException(
                status_code = status.HTTP_404_NOT_FOUND
                , detail    = f"Role '{role_code}' not found."
            )

        valid_services = {service.code for service in cls.list_services(session)}
        now_utc        = datetime.now(timezone.utc).replace(tzinfo=None)
        for perm in permissions:
            if perm.service_code not in valid_services:
                logger.warn(
                    "PermissionService.set_role_permissions: invalid service_code"
                    , f"role_code: {role_code}"
                    , f"service_code: {perm.service_code}"
                )
                raise HTTPException(
                    status_code = status.HTTP_400_BAD_REQUEST
                    , detail    = f"Invalid service_code: {perm.service_code}"
                )

            existing = (
                session.query(ROLE_PERMISSION_MODEL)
                .filter(
                    ROLE_PERMISSION_MODEL.role_code == role_code
                    , ROLE_PERMISSION_MODEL.service_code == perm.service_code
                )
                .first()
            )
            if existing:
                existing.can_read         = perm.can_read
                existing.can_write        = perm.can_write
                existing.can_update       = perm.can_update
                existing.can_delete       = perm.can_delete
                existing.updated_by       = username
                existing.updated_datetime = now_utc
            else:
                session.add(
                    ROLE_PERMISSION_MODEL(
                        role_code      = role_code
                        , service_code = perm.service_code
                        , can_read     = perm.can_read
                        , can_write    = perm.can_write
                        , can_update   = perm.can_update
                        , can_delete   = perm.can_delete
                        , created_by   = username
                    )
                )

        session.commit()
        logger.info(
            "PermissionService.set_role_permissions: updated"
            , f"role_code: {role_code}"
            , f"count: {len(permissions)}"
            , f"username: {username}"
        )
        return cls.get_role_permissions(session, role_code)


    @staticmethod
    def has_permission(
        session        : Session
        , role_code    : str
        , service_code : str
        , action       : PERMISSION_ACTION_ENUM
    ) -> bool:
        if role_code == ROLE_CODE_ENUM.ADMIN.value:
            return True

        perm = (
            session.query(ROLE_PERMISSION_MODEL)
            .filter(
                ROLE_PERMISSION_MODEL.role_code == role_code
                , ROLE_PERMISSION_MODEL.service_code == service_code
                , ROLE_PERMISSION_MODEL.status_code == STATUS_CODE_ENUM.ACTIVE.value
                , ROLE_PERMISSION_MODEL.deleted_datetime.is_(None)
            )
            .first()
        )
        if not perm:
            return False

        if action == PERMISSION_ACTION_ENUM.READ:
            return perm.can_read
        if action == PERMISSION_ACTION_ENUM.WRITE:
            return perm.can_write
        if action == PERMISSION_ACTION_ENUM.UPDATE:
            return perm.can_update
        if action == PERMISSION_ACTION_ENUM.DELETE:
            return perm.can_delete
        return False


    @staticmethod
    def enforce_department_scope(
        current_user             : USER_MODEL
        , target_department_code : Optional[str]
    ) -> None:
        """Resource-level guard: restrict non-ADMIN users to their assigned department_code."""
        if current_user.role_code == ROLE_CODE_ENUM.ADMIN.value:
            return
        if not target_department_code:
            return
        if current_user.department_code != target_department_code:
            logger.warn(
                "PermissionService.enforce_department_scope: denied"
                , f"username: {current_user.username}"
                , f"user_dept: {current_user.department_code}"
                , f"target_dept: {target_department_code}"
            )
            raise HTTPException(
                status_code = status.HTTP_403_FORBIDDEN
                , detail    = f"Access denied for department '{target_department_code}'."
            )


    @staticmethod
    def enforce_owner_or_admin(
        current_user     : USER_MODEL
        , owner_user_id  : Optional[UUID] = None
        , owner_username : Optional[str]  = None
    ) -> None:
        """Resource-level guard: allow ADMIN or the resource owner (by user_id or username)."""
        if current_user.role_code == ROLE_CODE_ENUM.ADMIN.value:
            return
        if owner_user_id is not None and current_user.id == owner_user_id:
            return
        if owner_username is not None and current_user.username == owner_username:
            return
        logger.warn(
            "PermissionService.enforce_owner_or_admin: denied"
            , f"username: {current_user.username}"
            , f"owner_user_id: {owner_user_id}"
            , f"owner_username: {owner_username}"
        )
        raise HTTPException(
            status_code = status.HTTP_403_FORBIDDEN
            , detail    = "Resource-level permission denied: you do not own this resource."
        )
