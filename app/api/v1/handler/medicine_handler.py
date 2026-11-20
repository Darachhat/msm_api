from typing import List, Optional
from uuid   import UUID

from fastapi        import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.deps.auth_deps      import get_current_user, require_roles
from app.core.db                 import getSession
from app.core.enum               import ROLE_CODE_ENUM
from app.models.auth_model       import USER_MODEL
from app.schemas.base_schema     import IResponseBase
from app.schemas.medicine_schema import (
    DepartmentResponse
    , MedicineCreate
    , MedicineResponse
    , MedicineUpdate
)
from app.services.medicine_service import MedicineService

router = APIRouter()


@router.get(
    ""
    , response_model = IResponseBase[List[MedicineResponse]]
    , summary        = "List medicines"
)
def list_medicines(
    category_code  : Optional[str]  = Query(None)
    , is_narcotic  : Optional[bool] = Query(None)
    , search       : Optional[str]  = Query(None)
    , limit        : int            = Query(100, ge = 1, le = 500)
    , offset       : int            = Query(0, ge = 0)
    , session      : Session        = Depends(getSession)
    , current_user : USER_MODEL     = Depends(get_current_user)
):
    rows = MedicineService.list_medicines(
        session         = session
        , category_code = category_code
        , is_narcotic   = is_narcotic
        , search        = search
        , limit         = limit
        , offset        = offset
    )
    return IResponseBase(data = [MedicineResponse.model_validate(r) for r in rows])


@router.post(
    ""
    , response_model = IResponseBase[MedicineResponse]
    , summary        = "Create medicine"
)
def create_medicine(
    payload        : MedicineCreate
    , session      : Session = Depends(getSession)
    , current_user : USER_MODEL = Depends(
        require_roles([ROLE_CODE_ENUM.ADMIN.value, ROLE_CODE_ENUM.PHARMACIST.value])
    )
):
    med = MedicineService.create_medicine(session, payload, current_user.username)
    return IResponseBase(
        data      = MedicineResponse.model_validate(med)
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
    , session      : Session = Depends(getSession)
    , current_user : USER_MODEL = Depends(
        require_roles([ROLE_CODE_ENUM.ADMIN.value, ROLE_CODE_ENUM.PHARMACIST.value])
    )
):
    med = MedicineService.update_medicine(session, medicine_id, payload, current_user.username)
    return IResponseBase(
        data      = MedicineResponse.model_validate(med)
        , message = "Medicine updated"
    )


@router.delete(
    "/{medicine_id}"
    , response_model = IResponseBase[dict]
    , summary        = "Soft-delete medicine"
)
def delete_medicine(
    medicine_id    : UUID
    , session      : Session = Depends(getSession)
    , current_user : USER_MODEL = Depends(require_roles([ROLE_CODE_ENUM.ADMIN.value]))
):
    MedicineService.delete_medicine(session, medicine_id, current_user.username)
    return IResponseBase(
        data      = {"id": str(medicine_id)}
        , message = "Medicine deleted"
    )


@router.get(
    "/departments"
    , response_model = IResponseBase[List[DepartmentResponse]]
    , summary        = "List departments"
)
def list_departments(
    session        : Session = Depends(getSession)
    , current_user : USER_MODEL = Depends(get_current_user)
):
    rows = MedicineService.list_departments(session)
    return IResponseBase(data = [DepartmentResponse.model_validate(r) for r in rows])
