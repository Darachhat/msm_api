from datetime import date
from typing   import List, Optional
from uuid     import UUID

from fastapi        import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.deps.auth_deps          import require_permission, require_resource_permission
from app.core.db                     import getSession
from app.core.enum                   import PERMISSION_ACTION_ENUM, SERVICE_MODULE_ENUM
from app.models.auth_model           import USER_MODEL
from app.schemas.base_schema         import IResponseBase
from app.schemas.dispensing_schema   import (
    DispensingCreate
    , DispensingResponse
    , DispensingUpdate
)
from app.services.dispensing_service import DispensingService
from app.services.permission_service import PermissionService

router = APIRouter()


@router.post(
    ""
    , response_model = IResponseBase[DispensingResponse]
    , summary        = "Create patient dispensing record"
)
def create_dispensing(
    payload        : DispensingCreate
    , session      : Session    = Depends(getSession)
    , current_user : USER_MODEL = Depends(
        require_permission(SERVICE_MODULE_ENUM.DISPENSING.value, PERMISSION_ACTION_ENUM.WRITE)
    )
):
    PermissionService.enforce_department_scope(current_user, payload.department_code)
    res = DispensingService.create_dispensing(session, payload, current_user.username)
    return IResponseBase(
        data      = res
        , message = "Dispensing record created"
    )


@router.get(
    ""
    , response_model = IResponseBase[List[DispensingResponse]]
    , summary        = "List patient dispensing records"
)
def list_dispensing(
    start_date        : Optional[date] = Query(None)
    , end_date        : Optional[date] = Query(None)
    , category_code   : Optional[str]  = Query(None)
    , department_code : Optional[str]  = Query(None)
    , limit           : int            = Query(100, ge = 1, le = 500)
    , offset          : int            = Query(0, ge = 0)
    , session         : Session        = Depends(getSession)
    , current_user    : USER_MODEL     = Depends(
        require_resource_permission(SERVICE_MODULE_ENUM.DISPENSING.value, PERMISSION_ACTION_ENUM.READ)
    )
):
    effective_dept = department_code or (
        None if current_user.role_code == "ADMIN" else current_user.department_code
    )
    res = DispensingService.list_dispensing(
        session           = session
        , start_date      = start_date
        , end_date        = end_date
        , category_code   = category_code
        , department_code = effective_dept
        , limit           = limit
        , offset          = offset
    )
    return IResponseBase(data = res)


@router.get(
    "/{dispensing_id}"
    , response_model = IResponseBase[DispensingResponse]
    , summary        = "Get dispensing record"
)
def get_dispensing(
    dispensing_id  : UUID
    , session      : Session    = Depends(getSession)
    , current_user : USER_MODEL = Depends(
        require_permission(SERVICE_MODULE_ENUM.DISPENSING.value, PERMISSION_ACTION_ENUM.READ)
    )
):
    res = DispensingService.get_dispensing(session, dispensing_id)
    PermissionService.enforce_department_scope(current_user, res.department_code)
    return IResponseBase(data = res)


@router.put(
    "/{dispensing_id}"
    , response_model = IResponseBase[DispensingResponse]
    , summary        = "Update dispensing record"
)
def update_dispensing(
    dispensing_id  : UUID
    , payload      : DispensingUpdate
    , session      : Session    = Depends(getSession)
    , current_user : USER_MODEL = Depends(
        require_permission(SERVICE_MODULE_ENUM.DISPENSING.value, PERMISSION_ACTION_ENUM.UPDATE)
    )
):
    existing = DispensingService.get_dispensing(session, dispensing_id)
    PermissionService.enforce_department_scope(current_user, existing.department_code)
    res = DispensingService.update_dispensing(session, dispensing_id, payload, current_user.username)
    return IResponseBase(
        data      = res
        , message = "Dispensing record updated"
    )


@router.delete(
    "/{dispensing_id}"
    , response_model = IResponseBase[dict]
    , summary        = "Delete dispensing record"
)
def delete_dispensing(
    dispensing_id  : UUID
    , session      : Session    = Depends(getSession)
    , current_user : USER_MODEL = Depends(
        require_permission(SERVICE_MODULE_ENUM.DISPENSING.value, PERMISSION_ACTION_ENUM.DELETE)
    )
):
    existing = DispensingService.get_dispensing(session, dispensing_id)
    PermissionService.enforce_department_scope(current_user, existing.department_code)
    DispensingService.delete_dispensing(session, dispensing_id, current_user.username)
    return IResponseBase(
        data      = {"id": str(dispensing_id)}
        , message = "Dispensing record deleted"
    )
