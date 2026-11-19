from typing import Optional

from fastapi        import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.deps.auth_deps         import require_permission
from app.core.db                    import getSession
from app.core.enum                  import PERMISSION_ACTION_ENUM, SERVICE_MODULE_ENUM
from app.models.auth_model          import USER_MODEL
from app.schemas.base_schema        import IResponseBase
from app.schemas.dashboard_schema   import DashboardSummaryResponse
from app.services.dashboard_service import DashboardService

router = APIRouter()


@router.get(
    ""
    , response_model = IResponseBase[DashboardSummaryResponse]
    , summary        = "Dashboard summary (stock by tab, patients, nearly expired batches)"
)
def get_dashboard(
    expiring_within_days : Optional[int] = Query(30, description = "Optional days threshold for nearly expired alert")
    , department_code    : Optional[str] = Query(None)
    , session            : Session = Depends(getSession)
    , current_user       : USER_MODEL = Depends(
        require_permission(SERVICE_MODULE_ENUM.DASHBOARD.value, PERMISSION_ACTION_ENUM.READ)
    )
):
    data = DashboardService.get_summary(session, expiring_within_days, department_code)
    return IResponseBase(data = data)
