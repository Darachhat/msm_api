from pathlib import Path
import sys
from uuid    import uuid4

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path     = [p for p in sys.path if "khmer" not in p.lower()]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import jwt
import pytest
from fastapi import HTTPException
from passlib.context import CryptContext

from app.core.rate_limiter import SlidingWindowRateLimiter
from app.core.security import (
    create_access_token
    , decode_token
    , generate_csrf_token
    , generate_opaque_refresh_token
    , hash_password
    , hash_token
    , needs_password_rehash
    , verify_csrf_token
    , verify_password
)
from app.core.system_log_utils import SystemLogUtils
from app.middleware.auth_middleware import AuthMiddleware
from app.models import auth_model, base_data_model, data_model, track_model
from app.models.base_model import Base
from app.services.permission_service import PermissionService
from app.services.r2_object_service import R2ObjectService
from main import app


class _DummyUser:

    def __init__(self, uid, username: str, role_code: str, department_code: str):
        self.id              = uid
        self.username        = username
        self.role_code       = role_code
        self.department_code = department_code


class _DummyRequest:

    def __init__(self, headers: dict):
        self.headers = headers


def test_argon2id_and_legacy_bcrypt_upgrade():
    argon_hash = hash_password("StrongPass!2026")
    assert argon_hash.startswith("$argon2id$")
    assert verify_password("StrongPass!2026", argon_hash) is True
    assert verify_password("wrong", argon_hash) is False
    assert needs_password_rehash(argon_hash) is False

    legacy_bcrypt = CryptContext(schemes = ["bcrypt"]).hash("LegacyPass!123")
    assert verify_password("LegacyPass!123", legacy_bcrypt) is True
    assert needs_password_rehash(legacy_bcrypt) is True


def test_rs256_access_jwt_and_opaque_refresh_token():
    uid   = str(uuid4())
    token = create_access_token(
        subject         = uid
        , token_version = 4
        , extra_claims  = {"role_code": "ADMIN"}
    )
    assert jwt.get_unverified_header(token)["alg"] == "RS256"

    decoded = decode_token(token, expected_type = "access")
    assert decoded["sub"] == uid
    assert decoded["ver"] == 4
    assert decoded["iss"] == "msm_api"
    assert decoded["aud"] == "msm_client"

    with pytest.raises(jwt.InvalidTokenError):
        decode_token(token, expected_type = "refresh")

    opaque = generate_opaque_refresh_token()
    assert len(opaque) >= 80
    assert "." not in opaque
    assert len(hash_token(opaque)) == 64


def test_csrf_double_submit():
    csrf = generate_csrf_token()
    assert verify_csrf_token(csrf, csrf) is True
    assert verify_csrf_token(csrf, "tampered") is False
    assert verify_csrf_token(None, csrf) is False


def test_sliding_window_rate_limiter():
    limiter = SlidingWindowRateLimiter(max_attempts = 3, window_seconds = 60)
    for _ in range(3):
        limiter.enforce(["ip:10.0.0.1"])
        limiter.record_attempt("ip:10.0.0.1")

    with pytest.raises(HTTPException) as exc_info:
        limiter.enforce(["ip:10.0.0.1"])
    assert exc_info.value.status_code == 429
    assert "Retry-After" in exc_info.value.headers

    limiter.reset("ip:10.0.0.1")
    limiter.enforce(["ip:10.0.0.1"])


def test_middleware_stack_and_auth_header_extraction():
    mw_names = [m.cls.__name__ for m in app.user_middleware]
    assert mw_names == ["TraceMiddleware", "CORSMiddleware", "AuthMiddleware", "LogMiddleware"]

    # /api/v1/auth/register must NOT be in SKIP_PREFIXES (Admin-only)
    assert "/api/v1/auth/register" not in AuthMiddleware.SKIP_PREFIXES

    assert AuthMiddleware._extract_auth(_DummyRequest({"X-API-Key": "secret"})) == ("API_KEY", "secret")
    assert AuthMiddleware._extract_auth(_DummyRequest({"Authorization": "Bearer abc"})) == ("BEARER", "abc")
    assert AuthMiddleware._extract_auth(_DummyRequest({"Authorization": "Basic xyz"})) == ("BASIC", "xyz")
    assert AuthMiddleware._extract_auth(_DummyRequest({})) == (None, None)


def test_all_auth_and_health_routes_registered():
    routes = {(list(r.methods)[0], r.path) for r in app.routes if hasattr(r, "methods") and r.methods}
    expected = {
        ("GET",    "/health")
        , ("GET",    "/health/ready")
        , ("POST",   "/api/v1/auth/register")
        , ("POST",   "/api/v1/auth/login")
        , ("POST",   "/api/v1/auth/refresh")
        , ("POST",   "/api/v1/auth/logout")
        , ("POST",   "/api/v1/auth/logout-all")
        , ("GET",    "/api/v1/auth/me")
        , ("POST",   "/api/v1/auth/change-password")
        , ("GET",    "/api/v1/auth/sessions")
        , ("DELETE", "/api/v1/auth/sessions/{session_id}")
    }
    assert expected.issubset(routes)


def test_resource_level_permissions():
    nurse = _DummyUser(uuid4(), "nurse1", "NURSE", "SURGICAL_ICU")
    admin = _DummyUser(uuid4(), "admin1", "ADMIN", "SURGICAL_ICU")

    PermissionService.enforce_department_scope(nurse, "SURGICAL_ICU")
    PermissionService.enforce_department_scope(admin, "CARDIOLOGY")
    with pytest.raises(HTTPException) as exc_info:
        PermissionService.enforce_department_scope(nurse, "CARDIOLOGY")
    assert exc_info.value.status_code == 403

    PermissionService.enforce_owner_or_admin(nurse, owner_user_id = nurse.id)
    with pytest.raises(HTTPException) as exc_info:
        PermissionService.enforce_owner_or_admin(nurse, owner_user_id = admin.id)
    assert exc_info.value.status_code == 403


def test_system_log_redaction_and_outbound_builder():
    headers = SystemLogUtils.sanitize_headers({"Authorization": "Bearer s3cr3t", "Accept": "application/json"})
    assert headers["Authorization"] == "***REDACTED***"
    assert headers["Accept"] == "application/json"

    body = SystemLogUtils.parse_body('{"username": "admin", "password": "secret"}')
    assert body["username"] == "admin"
    assert body["password"] == "***REDACTED***"

    captured = []
    original = SystemLogUtils.write_system_log_in_background
    SystemLogUtils.write_system_log_in_background = staticmethod(lambda data: captured.append(data))
    try:
        SystemLogUtils.store_outgoing_log(
            system_code        = "EXTERNAL_API"
            , request_endpoint = "https://api.example.com/v1/ping"
            , request_body     = {"token": "abc", "password": "hidden"}
            , response_code    = 200
            , response_body    = {"ok": True}
            , request_method   = "POST"
            , request_headers  = {"Authorization": "Bearer xyz"}
        )
    finally:
        SystemLogUtils.write_system_log_in_background = original

    assert len(captured) == 1
    assert captured[0].traffic_type == "OUTBOUND"
    assert captured[0].request_netloc == "https://api.example.com"
    assert captured[0].request_endpoint == "/v1/ping"
    assert captured[0].request_headers["Authorization"] == "***REDACTED***"
    assert captured[0].request_body["password"] == "***REDACTED***"


def test_all_models_inherit_base_audit_columns():
    required = {
        "status_code"
        , "created_datetime"
        , "updated_datetime"
        , "deleted_datetime"
        , "created_by"
        , "updated_by"
        , "deleted_by"
    }
    models = Base.__subclasses__()
    assert len(models) == 28
    for model_cls in models:
        assert required.issubset(set(model_cls.__table__.columns.keys()))

    # Verify schema placement after migrating 7 tables and deleting LOGIN_HISTORY_MODEL
    assert base_data_model.ROLE_MODEL.__table__.schema == "base_data"
    assert base_data_model.SERVICE_MODULE_MODEL.__table__.schema == "base_data"
    assert base_data_model.ROLE_PERMISSION_MODEL.__table__.schema == "base_data"
    assert data_model.USER_MODEL.__table__.schema == "data"
    assert data_model.REFRESH_TOKEN_MODEL.__table__.schema == "data"
    assert track_model.AUTH_AUDIT_LOG_MODEL.__table__.schema == "track"
    assert not hasattr(auth_model, "LOGIN_HISTORY_MODEL")


def test_r2_db_first_with_env_fallback(monkeypatch):
    # Reset caches
    R2ObjectService._cached_config    = None
    R2ObjectService._cache_expires_at = 0.0

    # 1. Verify DB config takes precedence when present
    monkeypatch.setattr(
        R2ObjectService
        , "_load_config_from_db"
        , classmethod(lambda cls: {
            "endpoint_url"               : "https://db-r2.example.com"
            , "access_key_id"            : "db_key"
            , "secret_access_key"        : "db_secret"
            , "bucket_name"              : "db-bucket"
            , "region"                   : "auto"
            , "presigned_expire_seconds" : 1800
        })
    )
    r2_cfg = R2ObjectService.resolve_config()
    assert r2_cfg["endpoint_url"] == "https://db-r2.example.com"
    assert r2_cfg["bucket_name"] == "db-bucket"

    # 2. Verify graceful fallback to .env when DB returns None
    R2ObjectService._cached_config    = None
    R2ObjectService._cache_expires_at = 0.0
    monkeypatch.setattr(R2ObjectService, "_load_config_from_db", classmethod(lambda cls: None))

    assert R2ObjectService.resolve_config()["region"] == "auto"


def test_frontend_integration_routes_registered():
    routes = {(list(r.methods)[0], r.path) for r in app.routes if hasattr(r, "methods") and r.methods}
    expected = {
        ("GET",    "/api/v1/medicines/forms")
        , ("GET",    "/api/v1/medicines")
        , ("POST",   "/api/v1/medicines")
        , ("PUT",    "/api/v1/medicines/{medicine_id}")
        , ("DELETE", "/api/v1/medicines/{medicine_id}")
        , ("GET",    "/api/v1/patients")
        , ("POST",   "/api/v1/patients")
        , ("GET",    "/api/v1/patients/{patient_id}")
        , ("PUT",    "/api/v1/patients/{patient_id}")
        , ("DELETE", "/api/v1/patients/{patient_id}")
        , ("GET",    "/api/v1/patients/usage-report")
        , ("GET",    "/api/v1/stock/batches")
        , ("POST",   "/api/v1/stock/batches/bulk")
        , ("PUT",    "/api/v1/stock/batches/{batch_id}")
        , ("DELETE", "/api/v1/stock/batches/{batch_id}")
        , ("POST",   "/api/v1/stock/writeoff")
        , ("DELETE", "/api/v1/stock/writeoff/{movement_id}")
        , ("GET",    "/api/v1/stock/movements")
        , ("GET",    "/api/v1/dispensing/items")
        , ("POST",   "/api/v1/dispensing/visit")
        , ("DELETE", "/api/v1/dispensing/items/{item_id}")
        , ("GET",    "/api/v1/dashboard")
        , ("GET",    "/api/v1/reports/data/stock-summary")
        , ("PUT",    "/api/v1/reports/data/requests")
        , ("GET",    "/api/v1/reports/data/daily-sheet")
        , ("GET",    "/api/v1/reports/data/narcotic")
        , ("GET",    "/api/v1/reports/data/medicine-usage")
        , ("GET",    "/api/v1/settings/roles")
        , ("POST",   "/api/v1/settings/roles")
        , ("PUT",    "/api/v1/settings/roles/{role_code}")
        , ("DELETE", "/api/v1/settings/roles/{role_code}")
        , ("GET",    "/api/v1/settings/login-history")
    }
    assert expected.issubset(routes)

