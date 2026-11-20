from typing import List, Optional
from uuid   import UUID

from fastapi        import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.deps.auth_deps      import get_current_user, require_permission
from app.core.db                 import getSession
from app.core.enum               import PERMISSION_ACTION_ENUM, SERVICE_MODULE_ENUM
from app.models.data_model       import USER_MODEL
from app.schemas.base_schema     import IResponseBase
from app.schemas.medicine_schema import (
    DepartmentResponse
    , MedicineCreate
    , MedicineFormResponse
    , MedicineResponse
    , MedicineUpdate
)
from app.services.medicine_service import MedicineService

router = APIRouter()


@router.get(
    "/forms"
    , response_model = IResponseBase[List[MedicineFormResponse]]
    , summary        = "List medicine forms"
)
def list_medicine_forms(
    session        : Session    = Depends(getSession)
    , current_user : USER_MODEL = Depends(get_current_user)
):
    rows = MedicineService.list_forms(session)
    return IResponseBase(data = [MedicineFormResponse.model_validate(r) for r in rows])


@router.get(
    "/departments"
    , response_model = IResponseBase[List[DepartmentResponse]]
    , summary        = "List departments"
)
def list_departments(
    session        : Session    = Depends(getSession)
    , current_user : USER_MODEL = Depends(get_current_user)
):
    rows = MedicineService.list_departments(session)
    return IResponseBase(data = [DepartmentResponse.model_validate(r) for r in rows])


@router.get(
    ""
    , response_model = IResponseBase[List[MedicineResponse]]
    , summary        = "List medicines (supports tabs, status_code, search, and with_stock)"
)
def list_medicines(
    category_code   : Optional[str]  = Query(None)
    , is_narcotic   : Optional[bool] = Query(None)
    , tabs          : Optional[str]  = Query(None, description = "Comma-separated: TABLET,INJECTION,NARCOTIC")
    , status_code   : Optional[str]  = Query("ACTIVE", description = "ACTIVE | INACTIVE | ALL")
    , with_stock    : bool           = Query(False)
    , search        : Optional[str]  = Query(None)
    , limit         : int            = Query(100, ge = 1, le = 1000)
    , offset        : int            = Query(0, ge = 0)
    , session       : Session        = Depends(getSession)
    , current_user  : USER_MODEL     = Depends(get_current_user)
):
    effective_dept = None if current_user.role_code == "ADMIN" else current_user.department_code
    rows = MedicineService.list_medicines(
        session           = session
        , category_code   = category_code
        , is_narcotic     = is_narcotic
        , tabs            = tabs
        , status_code     = status_code
        , search          = search
        , with_stock      = with_stock
        , department_code = effective_dept
        , limit           = limit
        , offset          = offset
    )
    return IResponseBase(data = rows, total = len(rows))


@router.post(
    ""
    , response_model = IResponseBase[MedicineResponse]
    , summary        = "Create medicine"
)
def create_medicine(
    payload        : MedicineCreate
    , session      : Session    = Depends(getSession)
    , current_user : USER_MODEL = Depends(
        require_permission(SERVICE_MODULE_ENUM.STOCK.value, PERMISSION_ACTION_ENUM.WRITE)
    )
):
    med = MedicineService.create_medicine(session, payload, current_user.username)
    return IResponseBase(
        data      = med
        , message = "Medicine created"
    )


@router.put(
    "/{medicine_id}"
    , response_model = IResponseBase[MedicineResponse]
    , summary        = "Update medicine"
)
def update_medicine(
    medicine_id    : UUID
    , payload      : MedicineUpdate
    , session      : Session    = Depends(getSession)
    , current_user : USER_MODEL = Depends(
        require_permission(SERVICE_MODULE_ENUM.STOCK.value, PERMISSION_ACTION_ENUM.UPDATE)
    )
):
    med = MedicineService.update_medicine(session, medicine_id, payload, current_user.username)
    return IResponseBase(
        data      = med
        , message = "Medicine updated"
    )


@router.delete(
    "/{medicine_id}"
    , response_model = IResponseBase[dict]
    , summary        = "Delete or deactivate medicine (deactivates if referenced by stock/dispensing)"
)
def delete_medicine(
    medicine_id    : UUID
    , session      : Session    = Depends(getSession)
    , current_user : USER_MODEL = Depends(
        require_permission(SERVICE_MODULE_ENUM.STOCK.value, PERMISSION_ACTION_ENUM.DELETE)
    )
):
    result = MedicineService.delete_medicine(session, medicine_id, current_user.username)
    return IResponseBase(
        data      = result
        , message = "Medicine deactivated" if result["deactivated"] else "Medicine deleted"
    )
