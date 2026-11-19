from datetime import date
from typing   import List, Optional
from uuid     import UUID

from fastapi        import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.deps.auth_deps        import get_current_user
from app.core.db                   import getSession
from app.models.auth_model         import USER_MODEL
from app.schemas.base_schema       import IResponseBase
from app.schemas.dispensing_schema import (
    DispensingCreate
    , DispensingResponse
    , DispensingUpdate
)
from app.services.dispensing_service import DispensingService

router = APIRouter()


@router.post(
    ""
    , response_model = IResponseBase[DispensingResponse]
    , summary        = "Create patient dispensing record"
)
def create_dispensing(
    payload        : DispensingCreate
    , session      : Session = Depends(getSession)
    , current_user : USER_MODEL = Depends(get_current_user)
):
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
    , category_code   : Optional[str] = Query(None)
    , department_code : Optional[str] = Query(None)
    , session         : Session = Depends(getSession)
    , current_user    : USER_MODEL = Depends(get_current_user)
):
    res = DispensingService.list_dispensing(session, start_date, end_date, category_code, department_code)
    return IResponseBase(data = res)


@router.get(
    "/{dispensing_id}"
    , response_model = IResponseBase[DispensingResponse]
    , summary        = "Get dispensing record"
)
def get_dispensing(
    dispensing_id  : UUID
    , session      : Session = Depends(getSession)
    , current_user : USER_MODEL = Depends(get_current_user)
):
    res = DispensingService.get_dispensing(session, dispensing_id)
    return IResponseBase(data = res)


@router.put(
    "/{dispensing_id}"
    , response_model = IResponseBase[DispensingResponse]
    , summary        = "Update dispensing record"
)
def update_dispensing(
    dispensing_id  : UUID
    , payload      : DispensingUpdate
    , session      : Session = Depends(getSession)
    , current_user : USER_MODEL = Depends(get_current_user)
):
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
    , session      : Session = Depends(getSession)
    , current_user : USER_MODEL = Depends(get_current_user)
):
    DispensingService.delete_dispensing(session, dispensing_id, current_user.username)
    return IResponseBase(
        data      = {"id": str(dispensing_id)}
        , message = "Dispensing record deleted"
    )
