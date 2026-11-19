from fastapi import APIRouter

from app.api.v1.handler import (
    auth_handler
    , dashboard_handler
    , dispensing_handler
    , file_handler
    , medicine_handler
    , patient_handler
    , report_handler
    , setting_handler
    , signature_handler
    , stock_handler
)

router = APIRouter()

router.include_router(auth_handler.router       , prefix = "/auth"        , tags = ["Auth"])
router.include_router(dashboard_handler.router  , prefix = "/dashboard"   , tags = ["Dashboard"])
router.include_router(patient_handler.router    , prefix = "/patients"    , tags = ["Patients"])
router.include_router(medicine_handler.router   , prefix = "/medicines"   , tags = ["Medicines & Base Data"])
router.include_router(dispensing_handler.router , prefix = "/dispensing"  , tags = ["Patient Dispensing"])
router.include_router(stock_handler.router      , prefix = "/stock"       , tags = ["Stock Ledger & Batches"])
router.include_router(signature_handler.router  , prefix = "/signatures"  , tags = ["Digital Signatures"])
router.include_router(report_handler.router     , prefix = "/reports"     , tags = ["Excel Reports"])
router.include_router(file_handler.router       , prefix = "/files"       , tags = ["Files (OSM Preview & Download)"])
router.include_router(setting_handler.router    , prefix = "/settings"    , tags = ["Settings (Users, Roles, Permissions, Login History)"])
