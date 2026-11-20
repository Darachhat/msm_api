from datetime import date
from typing   import List, Optional
from uuid     import UUID

from fastapi        import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.deps.auth_deps          import require_permission, require_resource_permission
from app.core.db                     import getSession
from app.core.enum                   import PERMISSION_ACTION_ENUM, SERVICE_MODULE_ENUM
from app.models.data_model           import USER_MODEL
from app.schemas.base_schema         import IResponseBase
from app.schemas.stock_schema        import (
    StockBatchBulkCreate
    , StockBatchCreate
    , StockBatchResponse
    , StockBatchUpdate
    , StockLedgerBatchUpsert
    , StockLedgerResponse
    , StockMovementResponse
    , StockWriteOffCreate
)
from app.services.permission_service import PermissionService
from app.services.stock_service      import StockService

router = APIRouter()


@router.post(
    "/batch"
    , response_model = IResponseBase[List[StockLedgerResponse]]
    , summary        = "Upsert daily stock ledger"
)
def batch_upsert_stock(
    payload        : StockLedgerBatchUpsert
    , session      : Session    = Depends(getSession)
    , current_user : USER_MODEL = Depends(
        require_permission(SERVICE_MODULE_ENUM.STOCK.value, PERMISSION_ACTION_ENUM.WRITE)
    )
):
    PermissionService.enforce_department_scope(current_user, payload.department_code)
    res = StockService.batch_upsert(session, payload, current_user.username)
    return IResponseBase(
        data      = res
        , message = "Stock ledger updated"
    )


@router.get(
    ""
    , response_model = IResponseBase[List[StockLedgerResponse]]
    , summary        = "List stock ledger entries"
)
def list_stock(
    stock_date        : Optional[date] = Query(None)
    , start_date      : Optional[date] = Query(None)
    , end_date        : Optional[date] = Query(None)
    , category_code   : Optional[str]  = Query(None)
    , department_code : Optional[str]  = Query(None)
    , limit           : int            = Query(100, ge = 1, le = 500)
    , offset          : int            = Query(0, ge = 0)
    , session         : Session        = Depends(getSession)
    , current_user    : USER_MODEL     = Depends(
        require_resource_permission(SERVICE_MODULE_ENUM.STOCK.value, PERMISSION_ACTION_ENUM.READ)
    )
):
    effective_dept = department_code or (
        None if current_user.role_code == "ADMIN" else current_user.department_code
    )
    res = StockService.list_stock(
        session           = session
        , stock_date      = stock_date
        , start_date      = start_date
        , end_date        = end_date
        , category_code   = category_code
        , department_code = effective_dept
        , limit           = limit
        , offset          = offset
    )
    return IResponseBase(data = res)


@router.post(
    "/batches"
    , response_model = IResponseBase[StockBatchResponse]
    , summary        = "Insert new stock batch"
)
def insert_stock_batch(
    payload        : StockBatchCreate
    , session      : Session    = Depends(getSession)
    , current_user : USER_MODEL = Depends(
        require_permission(SERVICE_MODULE_ENUM.STOCK.value, PERMISSION_ACTION_ENUM.WRITE)
    )
):
    PermissionService.enforce_department_scope(current_user, payload.department_code)
    res = StockService.insert_stock_batch(session, payload, current_user.username)
    return IResponseBase(
        data      = res
        , message = "Stock batch inserted"
    )


@router.post(
    "/batches/bulk"
    , response_model = IResponseBase[List[StockBatchResponse]]
    , summary        = "Bulk insert stock batches atomically"
)
def bulk_insert_stock_batches(
    payload        : StockBatchBulkCreate
    , session      : Session    = Depends(getSession)
    , current_user : USER_MODEL = Depends(
        require_permission(SERVICE_MODULE_ENUM.STOCK.value, PERMISSION_ACTION_ENUM.WRITE)
    )
):
    PermissionService.enforce_department_scope(current_user, payload.department_code)
    res = StockService.bulk_insert_batches(session, payload, current_user.username)
    return IResponseBase(
        data      = res
        , total   = len(res)
        , message = "Stock batches inserted"
    )


@router.put(
    "/batches/{batch_id}"
    , response_model = IResponseBase[StockBatchResponse]
    , summary        = "Update a stock batch"
)
def update_stock_batch(
    batch_id       : UUID
    , payload      : StockBatchUpdate
    , session      : Session    = Depends(getSession)
    , current_user : USER_MODEL = Depends(
        require_permission(SERVICE_MODULE_ENUM.STOCK.value, PERMISSION_ACTION_ENUM.UPDATE)
    )
):
    res = StockService.update_batch(session, batch_id, payload, current_user.username)
    return IResponseBase(
        data      = res
        , message = "Stock batch updated"
    )


@router.delete(
    "/batches/{batch_id}"
    , response_model = IResponseBase[dict]
    , summary        = "Delete an unused stock batch"
)
def delete_stock_batch(
    batch_id       : UUID
    , session      : Session    = Depends(getSession)
    , current_user : USER_MODEL = Depends(
        require_permission(SERVICE_MODULE_ENUM.STOCK.value, PERMISSION_ACTION_ENUM.DELETE)
    )
):
    StockService.delete_batch(session, batch_id, current_user.username)
    return IResponseBase(
        data      = {"id": str(batch_id)}
        , message = "Stock batch deleted"
    )


@router.get(
    "/batches"
    , response_model = IResponseBase[List[StockBatchResponse]]
    , summary        = "List stock batches (supports tab, medicine_id, availability, pagination)"
)
def list_stock_batches(
    tab                    : Optional[str]  = Query(None, description = "TABLET | INJECTION | NARCOTIC")
    , medicine_id          : Optional[UUID] = Query(None)
    , availability         : Optional[str]  = Query(None, description = "AVAILABLE | EXPIRING | EXPIRED")
    , department_code      : Optional[str]  = Query(None)
    , expiring_within_days : Optional[int]  = Query(None, description = "Optional expiry threshold in days")
    , limit                : int            = Query(100, ge = 1, le = 500)
    , offset               : int            = Query(0, ge = 0)
    , session              : Session        = Depends(getSession)
    , current_user         : USER_MODEL     = Depends(
        require_resource_permission(SERVICE_MODULE_ENUM.STOCK.value, PERMISSION_ACTION_ENUM.READ)
    )
):
    effective_dept = department_code or (
        None if current_user.role_code == "ADMIN" else current_user.department_code
    )
    rows, total = StockService.list_stock_batches(
        session                = session
        , tab                  = tab
        , medicine_id          = medicine_id
        , availability         = availability
        , department_code      = effective_dept
        , expiring_within_days = expiring_within_days
        , limit                = limit
        , offset               = offset
    )
    return IResponseBase(data = rows, total = total)


@router.post(
    "/writeoff"
    , response_model = IResponseBase[StockMovementResponse]
    , summary        = "Record a stock write-off (EXPIRED | DAMAGED | ADJUSTMENT)"
)
def create_writeoff(
    payload        : StockWriteOffCreate
    , session      : Session    = Depends(getSession)
    , current_user : USER_MODEL = Depends(
        require_permission(SERVICE_MODULE_ENUM.STOCK.value, PERMISSION_ACTION_ENUM.WRITE)
    )
):
    res = StockService.create_writeoff(session, payload, current_user.username)
    return IResponseBase(
        data      = res
        , message = "Write-off recorded"
    )


@router.delete(
    "/writeoff/{movement_id}"
    , response_model = IResponseBase[dict]
    , summary        = "Delete a stock write-off and restore batch remaining quantity"
)
def delete_writeoff(
    movement_id    : UUID
    , session      : Session    = Depends(getSession)
    , current_user : USER_MODEL = Depends(
        require_permission(SERVICE_MODULE_ENUM.STOCK.value, PERMISSION_ACTION_ENUM.DELETE)
    )
):
    StockService.delete_writeoff(session, movement_id, current_user.username)
    return IResponseBase(
        data      = {"id": str(movement_id)}
        , message = "Write-off deleted"
    )


@router.get(
    "/movements"
    , response_model = IResponseBase[List[StockMovementResponse]]
    , summary        = "List stock movements (IN, USAGE, EXPIRED, DAMAGED, ADJUSTMENT)"
)
def list_movements(
    medicine_id       : Optional[UUID] = Query(None)
    , department_code : Optional[str]  = Query(None)
    , limit           : int            = Query(100, ge = 1, le = 500)
    , session         : Session        = Depends(getSession)
    , current_user    : USER_MODEL     = Depends(
        require_resource_permission(SERVICE_MODULE_ENUM.STOCK.value, PERMISSION_ACTION_ENUM.READ)
    )
):
    effective_dept = department_code or (
        None if current_user.role_code == "ADMIN" else current_user.department_code
    )
    rows = StockService.list_movements(
        session           = session
        , medicine_id     = medicine_id
        , department_code = effective_dept
        , limit           = limit
    )
    return IResponseBase(data = rows, total = len(rows))
