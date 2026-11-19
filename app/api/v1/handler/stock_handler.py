from datetime import date
from typing   import List, Optional

from fastapi        import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.deps.auth_deps   import get_current_user
from app.core.db              import getSession
from app.models.auth_model    import USER_MODEL
from app.schemas.base_schema  import IResponseBase
from app.schemas.stock_schema import (
    StockBatchCreate
    , StockBatchResponse
    , StockLedgerBatchUpsert
    , StockLedgerResponse
)
from app.services.stock_service import StockService

router = APIRouter()


@router.post(
    "/batch"
    , response_model = IResponseBase[List[StockLedgerResponse]]
    , summary        = "Upsert daily stock ledger"
)
def batch_upsert_stock(
    payload        : StockLedgerBatchUpsert
    , session      : Session = Depends(getSession)
    , current_user : USER_MODEL = Depends(get_current_user)
):
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
    , category_code   : Optional[str] = Query(None)
    , department_code : Optional[str] = Query(None)
    , session         : Session = Depends(getSession)
    , current_user    : USER_MODEL = Depends(get_current_user)
):
    res = StockService.list_stock(session, stock_date, start_date, end_date, category_code, department_code)
    return IResponseBase(data = res)


@router.post(
    "/batches"
    , response_model = IResponseBase[StockBatchResponse]
    , summary        = "Insert new stock batch (all types)"
)
def insert_stock_batch(
    payload        : StockBatchCreate
    , session      : Session = Depends(getSession)
    , current_user : USER_MODEL = Depends(get_current_user)
):
    res = StockService.insert_stock_batch(session, payload, current_user.username)
    return IResponseBase(
        data      = res
        , message = "Stock batch inserted"
    )


@router.get(
    "/batches"
    , response_model = IResponseBase[List[StockBatchResponse]]
    , summary        = "List stock batches by tab (TABLET | INJECTION | NARCOTIC)"
)
def list_stock_batches(
    tab                  : Optional[str] = Query(None, description = "TABLET | INJECTION | NARCOTIC")
    , department_code    : Optional[str] = Query(None)
    , expiring_within_days : Optional[int] = Query(None, description = "Optional expiry threshold in days")
    , session            : Session = Depends(getSession)
    , current_user       : USER_MODEL = Depends(get_current_user)
):
    res = StockService.list_stock_batches(session, tab, department_code, expiring_within_days)
    return IResponseBase(data = res)
