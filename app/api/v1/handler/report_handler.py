from typing import List, Optional

from fastapi        import APIRouter, Depends, Query
from sqlalchemy.orm import Session, joinedload

from app.api.deps.auth_deps            import get_current_user
from app.core.db                       import getSession
from app.core.enum                     import STATUS_CODE_ENUM
from app.models.auth_model             import USER_MODEL
from app.models.data_model             import REPORT_EXPORT_MODEL
from app.schemas.base_schema           import IResponseBase
from app.schemas.report_schema         import ReportExportResponse, ReportGenerateRequest
from app.services.excel_report_service import ExcelReportService

router = APIRouter()


@router.post(
    "/generate"
    , response_model = IResponseBase[ReportExportResponse]
    , summary        = "Generate Excel report, upload to R2, and return preview/download URLs"
)
def generate_report(
    payload        : ReportGenerateRequest
    , session      : Session = Depends(getSession)
    , current_user : USER_MODEL = Depends(get_current_user)
):
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
    , session         : Session = Depends(getSession)
    , current_user    : USER_MODEL = Depends(get_current_user)
):
    query = (
        session.query(REPORT_EXPORT_MODEL)
        .options(joinedload(REPORT_EXPORT_MODEL.file_object))
        .filter(
            REPORT_EXPORT_MODEL.status_code == STATUS_CODE_ENUM.ACTIVE.value
            , REPORT_EXPORT_MODEL.deleted_datetime.is_(None)
        )
    )
    if report_type_code:
        query = query.filter(REPORT_EXPORT_MODEL.report_type_code == report_type_code)
    if department_code:
        query = query.filter(REPORT_EXPORT_MODEL.department_code == department_code)

    rows = query.order_by(REPORT_EXPORT_MODEL.created_datetime.desc()).limit(100).all()
    return IResponseBase(data = [ReportExportResponse.model_validate(r) for r in rows])
