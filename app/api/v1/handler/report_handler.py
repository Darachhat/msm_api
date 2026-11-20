from typing import List, Optional

from fastapi        import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.deps.auth_deps            import require_permission, require_resource_permission
from app.core.db                       import getSession
from app.core.enum                     import PERMISSION_ACTION_ENUM, SERVICE_MODULE_ENUM
from app.models.data_model             import USER_MODEL
from app.schemas.base_schema           import IResponseBase
from app.schemas.report_schema         import ReportExportResponse, ReportGenerateRequest
from app.services.excel_report_service import ExcelReportService
from app.services.permission_service   import PermissionService

router = APIRouter()


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
