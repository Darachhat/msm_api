from typing import List, Optional
from uuid   import UUID

from fastapi        import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.deps.auth_deps     import require_permission
from app.core.db                import getSession
from app.core.enum              import PERMISSION_ACTION_ENUM, SERVICE_MODULE_ENUM
from app.models.auth_model      import USER_MODEL
from app.schemas.auth_schema    import UserResponse
from app.schemas.base_schema    import IResponseBase
from app.schemas.setting_schema import (
    LoginHistoryResponse
    , RoleCreate
    , RolePermissionInput
    , RolePermissionResponse
    , RoleResponse
    , ServiceModuleResponse
    , UserCreateByAdmin
    , UserUpdateByAdmin
)
from app.services.permission_service import PermissionService
from app.services.setting_service    import SettingService

router = APIRouter()


# --- Users ---
@router.get(
    "/users"
    , response_model = IResponseBase[List[UserResponse]]
    , summary        = "List users"
)
def list_users(
    search         : Optional[str] = Query(None)
    , session      : Session = Depends(getSession)
    , current_user : USER_MODEL = Depends(
        require_permission(SERVICE_MODULE_ENUM.SETTING.value, PERMISSION_ACTION_ENUM.READ)
    )
):
    users = SettingService.list_users(session, search)
    return IResponseBase(data = [UserResponse.model_validate(u) for u in users])


@router.post(
    "/users"
    , response_model = IResponseBase[UserResponse]
    , summary        = "Create user"
)
def create_user(
    payload        : UserCreateByAdmin
    , session      : Session = Depends(getSession)
    , current_user : USER_MODEL = Depends(
        require_permission(SERVICE_MODULE_ENUM.SETTING.value, PERMISSION_ACTION_ENUM.WRITE)
    )
):
    user = SettingService.create_user(session, payload, current_user.username)
    return IResponseBase(
        data      = UserResponse.model_validate(user)
        , message = "User created"
    )


@router.put(
    "/users/{user_id}"
    , response_model = IResponseBase[UserResponse]
    , summary        = "Update user"
)
def update_user(
    user_id        : UUID
    , payload      : UserUpdateByAdmin
    , session      : Session = Depends(getSession)
    , current_user : USER_MODEL = Depends(
        require_permission(SERVICE_MODULE_ENUM.SETTING.value, PERMISSION_ACTION_ENUM.UPDATE)
    )
):
    user = SettingService.update_user(session, user_id, payload, current_user.username)
    return IResponseBase(
        data      = UserResponse.model_validate(user)
        , message = "User updated"
    )


@router.delete(
    "/users/{user_id}"
    , response_model = IResponseBase[dict]
    , summary        = "Soft-delete user"
)
def delete_user(
    user_id        : UUID
    , session      : Session = Depends(getSession)
    , current_user : USER_MODEL = Depends(
        require_permission(SERVICE_MODULE_ENUM.SETTING.value, PERMISSION_ACTION_ENUM.DELETE)
    )
):
    SettingService.delete_user(session, user_id, current_user.username)
    return IResponseBase(
        data      = {"id": str(user_id)}
        , message = "User deleted"
    )


# --- Services & Roles / Permissions ---
@router.get(
    "/services"
    , response_model = IResponseBase[List[ServiceModuleResponse]]
    , summary        = "List controllable services"
)
def list_services(
    session        : Session = Depends(getSession)
    , current_user : USER_MODEL = Depends(
        require_permission(SERVICE_MODULE_ENUM.SETTING.value, PERMISSION_ACTION_ENUM.READ)
    )
):
    rows = PermissionService.list_services(session)
    return IResponseBase(data = [ServiceModuleResponse.model_validate(r) for r in rows])


@router.get(
    "/roles"
    , response_model = IResponseBase[List[RoleResponse]]
    , summary        = "List roles with service permissions"
)
def list_roles(
    session        : Session = Depends(getSession)
    , current_user : USER_MODEL = Depends(
        require_permission(SERVICE_MODULE_ENUM.SETTING.value, PERMISSION_ACTION_ENUM.READ)
    )
):
    return IResponseBase(data = SettingService.list_roles(session))


@router.post(
    "/roles"
    , response_model = IResponseBase[RoleResponse]
    , summary        = "Create role with service permissions"
)
def create_role(
    payload        : RoleCreate
    , session      : Session = Depends(getSession)
    , current_user : USER_MODEL = Depends(
        require_permission(SERVICE_MODULE_ENUM.SETTING.value, PERMISSION_ACTION_ENUM.WRITE)
    )
):
    res = SettingService.create_role(session, payload, current_user.username)
    return IResponseBase(
        data      = res
        , message = "Role created"
    )


@router.put(
    "/roles/{role_code}/permissions"
    , response_model = IResponseBase[List[RolePermissionResponse]]
    , summary        = "Set Read/Write/Update/Delete permissions for a role by service"
)
def set_role_permissions(
    role_code      : str
    , permissions  : List[RolePermissionInput]
    , session      : Session = Depends(getSession)
    , current_user : USER_MODEL = Depends(
        require_permission(SERVICE_MODULE_ENUM.SETTING.value, PERMISSION_ACTION_ENUM.UPDATE)
    )
):
    perms = PermissionService.set_role_permissions(session, role_code, permissions, current_user.username)
    return IResponseBase(
        data      = [RolePermissionResponse.model_validate(p) for p in perms]
        , message = "Role permissions updated"
    )


# --- Login History ---
@router.get(
    "/login-history"
    , response_model = IResponseBase[List[LoginHistoryResponse]]
    , summary        = "List login history"
)
def list_login_history(
    username       : Optional[str] = Query(None)
    , login_status : Optional[str] = Query(None, description = "SUCCESS | FAILED")
    , limit        : int = Query(100, ge = 1, le = 500)
    , session      : Session = Depends(getSession)
    , current_user : USER_MODEL = Depends(
        require_permission(SERVICE_MODULE_ENUM.SETTING.value, PERMISSION_ACTION_ENUM.READ)
    )
):
    rows = SettingService.list_login_history(session, username, login_status, limit)
    return IResponseBase(data = [LoginHistoryResponse.model_validate(r) for r in rows])
