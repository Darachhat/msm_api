from datetime import date
from typing   import List, Optional
from uuid     import UUID

from fastapi        import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.deps.auth_deps     import require_permission
from app.core.db                import getSession
from app.core.enum              import PERMISSION_ACTION_ENUM, SERVICE_MODULE_ENUM
from app.models.data_model      import USER_MODEL
from app.schemas.base_schema    import IResponseBase
from app.schemas.patient_schema import (
    PatientCreate
    , PatientResponse
    , PatientUpdate
    , PatientUsageReportResponse
)
from app.services.patient_service import PatientService

router = APIRouter()


@router.post(
    ""
    , response_model = IResponseBase[PatientResponse]
    , summary        = "Insert new patient"
)
def create_patient(
    payload        : PatientCreate
    , session      : Session    = Depends(getSession)
    , current_user : USER_MODEL = Depends(
        require_permission(SERVICE_MODULE_ENUM.PATIENT.value, PERMISSION_ACTION_ENUM.WRITE)
    )
):
    patient = PatientService.create_patient(session, payload, current_user.username)
    return IResponseBase(
        data      = patient
        , message = "Patient created"
    )


@router.get(
    ""
    , response_model = IResponseBase[List[PatientResponse]]
    , summary        = "List patients (filterable by search/name, admission_status, and date range)"
)
def list_patients(
    name               : Optional[str]  = Query(None, description = "Filter by patient name")
    , search           : Optional[str]  = Query(None, description = "Search by name, code, or diagnosis")
    , admission_status : Optional[str]  = Query(None, description = "ADMITTED | DISCHARGED")
    , date_in          : Optional[date] = Query(None)
    , start_date       : Optional[date] = Query(None)
    , end_date         : Optional[date] = Query(None)
    , limit            : int            = Query(100, ge = 1, le = 500)
    , offset           : int            = Query(0, ge = 0)
    , session          : Session        = Depends(getSession)
    , current_user     : USER_MODEL     = Depends(
        require_permission(SERVICE_MODULE_ENUM.PATIENT.value, PERMISSION_ACTION_ENUM.READ)
    )
):
    rows, total = PatientService.list_patients(
        session            = session
        , name             = name
        , search           = search
        , admission_status = admission_status
        , date_in          = date_in
        , start_date       = start_date
        , end_date         = end_date
        , limit            = limit
        , offset           = offset
    )
    return IResponseBase(data = rows, total = total)


@router.get(
    "/usage-report"
    , response_model = IResponseBase[List[PatientUsageReportResponse]]
    , summary        = "Patient medicine usage summary (Daily, Weekly, Monthly)"
)
def patient_usage_report(
    start_date     : date           = Query(...)
    , period       : str            = Query("DAILY", description = "DAILY | WEEKLY | MONTHLY")
    , end_date     : Optional[date] = Query(None)
    , tabs         : Optional[str]  = Query(None, description = "Comma-separated: TABLET,INJECTION,NARCOTIC")
    , patient_id   : Optional[UUID] = Query(None)
    , patient_name : Optional[str]  = Query(None)
    , session      : Session        = Depends(getSession)
    , current_user : USER_MODEL     = Depends(
        require_permission(SERVICE_MODULE_ENUM.REPORT.value, PERMISSION_ACTION_ENUM.READ)
    )
):
    data = PatientService.get_patient_usage_report(
        session        = session
        , start_date   = start_date
        , period       = period
        , end_date     = end_date
        , tabs         = tabs
        , patient_id   = patient_id
        , patient_name = patient_name
    )
    return IResponseBase(data = data)


@router.get(
    "/{patient_id}"
    , response_model = IResponseBase[PatientResponse]
    , summary        = "Get patient by ID"
)
def get_patient(
    patient_id     : UUID
    , session      : Session    = Depends(getSession)
    , current_user : USER_MODEL = Depends(
        require_permission(SERVICE_MODULE_ENUM.PATIENT.value, PERMISSION_ACTION_ENUM.READ)
    )
):
    patient = PatientService.get_patient(session, patient_id)
    return IResponseBase(data = PatientService.to_response(patient))


@router.put(
    "/{patient_id}"
    , response_model = IResponseBase[PatientResponse]
    , summary        = "Update patient"
)
def update_patient(
    patient_id     : UUID
    , payload      : PatientUpdate
    , session      : Session    = Depends(getSession)
    , current_user : USER_MODEL = Depends(
        require_permission(SERVICE_MODULE_ENUM.PATIENT.value, PERMISSION_ACTION_ENUM.UPDATE)
    )
):
    patient = PatientService.update_patient(session, patient_id, payload, current_user.username)
    return IResponseBase(
        data      = patient
        , message = "Patient updated"
    )


@router.delete(
    "/{patient_id}"
    , response_model = IResponseBase[dict]
    , summary        = "Soft-delete patient"
)
def delete_patient(
    patient_id     : UUID
    , session      : Session    = Depends(getSession)
    , current_user : USER_MODEL = Depends(
        require_permission(SERVICE_MODULE_ENUM.PATIENT.value, PERMISSION_ACTION_ENUM.DELETE)
    )
):
    PatientService.delete_patient(session, patient_id, current_user.username)
    return IResponseBase(
        data      = {"id": str(patient_id)}
        , message = "Patient deleted"
    )
