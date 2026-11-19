from datetime import datetime
from typing   import List

from fastapi        import HTTPException, status
from sqlalchemy.orm import Session

from app.core.enum              import PERMISSION_ACTION_ENUM, STATUS_CODE_ENUM
from app.models.auth_model      import ROLE_MODEL, ROLE_PERMISSION_MODEL, SERVICE_MODULE_MODEL
from app.schemas.setting_schema import RolePermissionInput


class PermissionService:
    """Dedicated RBAC service managing per-role, per-service Read/Write/Update/Delete permissions."""

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
    def set_role_permissions(
        cls
        , session     : Session
        , role_code   : str
        , permissions : List[RolePermissionInput]
        , username    : str
    ) -> List[ROLE_PERMISSION_MODEL]:
        role = session.query(ROLE_MODEL).filter(ROLE_MODEL.code == role_code).first()
        if not role:
            raise HTTPException(
                status_code = status.HTTP_404_NOT_FOUND
                , detail    = f"Role '{role_code}' not found."
            )

        valid_services = {s.code for s in cls.list_services(session)}
        for perm in permissions:
            if perm.service_code not in valid_services:
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
                existing.updated_datetime = datetime.utcnow()
            else:
                session.add(
                    ROLE_PERMISSION_MODEL(
                        role_code       = role_code
                        , service_code  = perm.service_code
                        , can_read      = perm.can_read
                        , can_write     = perm.can_write
                        , can_update    = perm.can_update
                        , can_delete    = perm.can_delete
                        , created_by    = username
                    )
                )

        session.commit()
        return cls.get_role_permissions(session, role_code)


    @staticmethod
    def has_permission(
        session        : Session
        , role_code    : str
        , service_code : str
        , action       : PERMISSION_ACTION_ENUM
    ) -> bool:
        if role_code == "ADMIN":
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
