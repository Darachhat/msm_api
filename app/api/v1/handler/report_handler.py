from datetime import date
from typing   import List, Optional
from uuid     import UUID

from fastapi        import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.deps.auth_deps            import require_permission, require_resource_permission
from app.core.db                       import getSession
from app.core.enum                     import PERMISSION_ACTION_ENUM, SERVICE_MODULE_ENUM
from app.models.data_model             import USER_MODEL
from app.schemas.base_schema           import IResponseBase
from app.schemas.dispensing_schema     import DispensingLineResponse
from app.schemas.report_schema         import (
    DailySheetReportResponse
    , MedicineUsageReportResponse
    , ReportExportResponse
    , ReportGenerateRequest
    , ReportRequestsUpsert
    , StockSummaryReportResponse
)
from app.services.excel_report_service import ExcelReportService
from app.services.permission_service   import PermissionService
from app.services.report_data_service  import ReportDataService

router = APIRouter()


# --- JSON Report Data Endpoints (consumed by msm_front report screens) ---

@router.get(
    "/data/stock-summary"
    , response_model = IResponseBase[StockSummaryReportResponse]
    , summary        = "Stock summary report data (opening, received, daily used, write-off, closing, requisition)"
)
def get_stock_summary_report(
    start_date        : date          = Query(...)
    , end_date        : date          = Query(...)
    , tabs            : Optional[str] = Query(None, description = "Comma-separated: TABLET,INJECTION,NARCOTIC")
    , department_code : Optional[str] = Query(None)
    , session         : Session       = Depends(getSession)
    , current_user    : USER_MODEL    = Depends(
        require_resource_permission(SERVICE_MODULE_ENUM.REPORT.value, PERMISSION_ACTION_ENUM.READ)
    )
):
    effective_dept = department_code or (
        None if current_user.role_code == "ADMIN" else current_user.department_code
    )
    data = ReportDataService.stock_summary(
        session           = session
        , start_date      = start_date
        , end_date        = end_date
        , tabs            = tabs
        , department_code = effective_dept
    )
    return IResponseBase(data = data)


@router.put(
    "/data/requests"
    , response_model = IResponseBase[dict]
    , summary        = "Save requested and supplied quantities for a report period"
)
def save_report_requests(
    payload        : ReportRequestsUpsert
    , session      : Session    = Depends(getSession)
    , current_user : USER_MODEL = Depends(
        require_permission(SERVICE_MODULE_ENUM.REPORT.value, PERMISSION_ACTION_ENUM.WRITE)
    )
):
    PermissionService.enforce_department_scope(current_user, payload.department_code)
    count = ReportDataService.save_requests(session, payload, current_user.username)
    return IResponseBase(
        data      = {"saved": count}
        , message = "Requisition quantities saved"
    )


@router.get(
    "/data/daily-sheet"
    , response_model = IResponseBase[DailySheetReportResponse]
    , summary        = "Daily sheet matrix (patients x medicines) for a date or period"
)
def get_daily_sheet_report(
    start_date        : date          = Query(...)
    , end_date        : date          = Query(...)
    , tabs            : Optional[str] = Query(None)
    , all_columns     : bool          = Query(False)
    , department_code : Optional[str] = Query(None)
    , session         : Session       = Depends(getSession)
    , current_user    : USER_MODEL    = Depends(
        require_resource_permission(SERVICE_MODULE_ENUM.REPORT.value, PERMISSION_ACTION_ENUM.READ)
    )
):
    effective_dept = department_code or (
        None if current_user.role_code == "ADMIN" else current_user.department_code
    )
    data = ReportDataService.daily_sheet(
        session           = session
        , start_date      = start_date
        , end_date        = end_date
        , tabs            = tabs
        , all_columns     = all_columns
        , department_code = effective_dept
    )
    return IResponseBase(data = data)


@router.get(
    "/data/narcotic"
    , response_model = IResponseBase[List[DispensingLineResponse]]
    , summary        = "Narcotic dispensing register lines for a date range"
)
def get_narcotic_report(
    start_date        : date           = Query(...)
    , end_date        : date           = Query(...)
    , medicine_id     : Optional[UUID] = Query(None)
    , department_code : Optional[str]  = Query(None)
    , session         : Session        = Depends(getSession)
    , current_user    : USER_MODEL     = Depends(
        require_resource_permission(SERVICE_MODULE_ENUM.REPORT.value, PERMISSION_ACTION_ENUM.READ)
    )
):
    effective_dept = department_code or (
        None if current_user.role_code == "ADMIN" else current_user.department_code
    )
    rows = ReportDataService.narcotic_lines(
        session           = session
        , start_date      = start_date
        , end_date        = end_date
        , medicine_id     = medicine_id
        , department_code = effective_dept
    )
    return IResponseBase(data = rows, total = len(rows))


@router.get(
    "/data/medicine-usage"
    , response_model = IResponseBase[MedicineUsageReportResponse]
    , summary        = "Medicine usage breakdown by patient for a date range"
)
def get_medicine_usage_report(
    start_date        : date           = Query(...)
    , end_date        : date           = Query(...)
    , tabs            : Optional[str]  = Query(None)
    , medicine_id     : Optional[UUID] = Query(None)
    , department_code : Optional[str]  = Query(None)
    , session         : Session        = Depends(getSession)
    , current_user    : USER_MODEL     = Depends(
        require_resource_permission(SERVICE_MODULE_ENUM.REPORT.value, PERMISSION_ACTION_ENUM.READ)
    )
):
    effective_dept = department_code or (
        None if current_user.role_code == "ADMIN" else current_user.department_code
    )
    data = ReportDataService.medicine_usage(
        session           = session
        , start_date      = start_date
        , end_date        = end_date
        , tabs            = tabs
        , medicine_id     = medicine_id
        , department_code = effective_dept
    )
    return IResponseBase(data = data)


# --- Excel Export Endpoints ---

@router.post(
    "/generate"
    , response_model = IResponseBase[ReportExportResponse]
    , summary        = "Generate Excel report, upload to R2, and return preview/download URLs"
)
def generate_report(
    payload        : ReportGenerateRequest
    , session      : Session    = Depends(getSession)
    , current_user : USER_MODEL = Depends(
        require_permission(SERVICE_MODULE_ENUM.REPORT.value, PERMISSION_ACTION_ENUM.WRITE)
    )
):
    PermissionService.enforce_department_scope(current_user, payload.department_code)
    export_row = ExcelReportService.generate_report(session, payload, current_user.username)
    return IResponseBase(
        data      = ReportExportResponse.model_validate(export_row)
        , message = "Report generated and uploaded to R2 successfully"
    )


@router.get(
    ""
    , response_model = IResponseBase[List[ReportExportResponse]]
    , summary        = "List generated reports"
)
def list_reports(
    report_type_code  : Optional[str] = Query(None)
    , department_code : Optional[str] = Query(None)
    , limit           : int           = Query(100, ge = 1, le = 500)
    , offset          : int           = Query(0, ge = 0)
    , session         : Session       = Depends(getSession)
    , current_user    : USER_MODEL    = Depends(
        require_resource_permission(SERVICE_MODULE_ENUM.REPORT.value, PERMISSION_ACTION_ENUM.READ)
    )
):
    effective_dept = department_code or (
        None if current_user.role_code == "ADMIN" else current_user.department_code
    )
    rows = ExcelReportService.list_reports(
        session            = session
        , report_type_code = report_type_code
        , department_code  = effective_dept
        , limit            = limit
        , offset           = offset
    )
    return IResponseBase(data = [ReportExportResponse.model_validate(r) for r in rows])
