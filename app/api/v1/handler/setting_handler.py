from datetime import date
from typing   import List, Optional
from uuid     import UUID

from fastapi        import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.deps.auth_deps     import require_permission
from app.core.db                import getSession
from app.core.enum              import PERMISSION_ACTION_ENUM, SERVICE_MODULE_ENUM
from app.models.data_model      import USER_MODEL
from app.schemas.auth_schema    import UserResponse
from app.schemas.base_schema    import IResponseBase
from app.schemas.setting_schema import (
    LoginHistoryResponse
    , RoleCreate
    , RolePermissionInput
    , RolePermissionResponse
    , RoleResponse
    , RoleUpdate
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
    , limit        : int           = Query(100, ge = 1, le = 500)
    , offset       : int           = Query(0, ge = 0)
    , session      : Session       = Depends(getSession)
    , current_user : USER_MODEL    = Depends(
        require_permission(SERVICE_MODULE_ENUM.SETTING.value, PERMISSION_ACTION_ENUM.READ)
    )
):
    users = SettingService.list_users(session, search = search, limit = limit, offset = offset)
    return IResponseBase(data = [UserResponse.model_validate(u) for u in users])


@router.post(
    "/users"
    , response_model = IResponseBase[UserResponse]
    , summary        = "Create user"
)
def create_user(
    payload        : UserCreateByAdmin
    , session      : Session    = Depends(getSession)
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
    , session      : Session    = Depends(getSession)
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
    , session      : Session    = Depends(getSession)
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
    session        : Session    = Depends(getSession)
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
    session        : Session    = Depends(getSession)
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
    , session      : Session    = Depends(getSession)
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
    "/roles/{role_code}"
    , response_model = IResponseBase[RoleResponse]
    , summary        = "Update role metadata and service permissions"
)
def update_role(
    role_code      : str
    , payload      : RoleUpdate
    , session      : Session    = Depends(getSession)
    , current_user : USER_MODEL = Depends(
        require_permission(SERVICE_MODULE_ENUM.SETTING.value, PERMISSION_ACTION_ENUM.UPDATE)
    )
):
    res = SettingService.update_role(session, role_code, payload, current_user.username)
    return IResponseBase(
        data      = res
        , message = "Role updated"
    )


@router.delete(
    "/roles/{role_code}"
    , response_model = IResponseBase[dict]
    , summary        = "Soft-delete role (if not system role and no users assigned)"
)
def delete_role(
    role_code      : str
    , session      : Session    = Depends(getSession)
    , current_user : USER_MODEL = Depends(
        require_permission(SERVICE_MODULE_ENUM.SETTING.value, PERMISSION_ACTION_ENUM.DELETE)
    )
):
    SettingService.delete_role(session, role_code, current_user.username)
    return IResponseBase(
        data      = {"code": role_code}
        , message = "Role deleted"
    )


@router.put(
    "/roles/{role_code}/permissions"
    , response_model = IResponseBase[List[RolePermissionResponse]]
    , summary        = "Set Read/Write/Update/Delete permissions for a role by service"
)
def set_role_permissions(
    role_code      : str
    , permissions  : List[RolePermissionInput]
    , session      : Session    = Depends(getSession)
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
    username       : Optional[str]  = Query(None)
    , user_id      : Optional[UUID] = Query(None)
    , login_status : Optional[str]  = Query(None, description = "SUCCESS | FAILED")
    , start_date   : Optional[date] = Query(None)
    , end_date     : Optional[date] = Query(None)
    , limit        : int            = Query(100, ge = 1, le = 500)
    , offset       : int            = Query(0, ge = 0)
    , session      : Session        = Depends(getSession)
    , current_user : USER_MODEL     = Depends(
        require_permission(SERVICE_MODULE_ENUM.SETTING.value, PERMISSION_ACTION_ENUM.READ)
    )
):
    rows, total = SettingService.list_login_history(
        session        = session
        , username     = username
        , user_id      = user_id
        , login_status = login_status
        , start_date   = start_date
        , end_date     = end_date
        , limit        = limit
        , offset       = offset
    )
    return IResponseBase(data = rows, total = total)
