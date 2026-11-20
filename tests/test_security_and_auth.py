from uuid import uuid4

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
from app.services.email_service import EmailService
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
        , ("POST",   "/api/v1/auth/forgot-password")
        , ("POST",   "/api/v1/auth/reset-password")
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
    assert len(models) == 29
    for model_cls in models:
        assert required.issubset(set(model_cls.__table__.columns.keys()))


def test_pluggable_email_service():
    sent = []
    EmailService.register_sender(lambda to, subj, body: sent.append((to, subj, body)))
    try:
        dispatched = EmailService.send_password_reset_email(
            to_email      = "staff@hospital.local"
            , username    = "nurse1"
            , reset_url   = "http://localhost:3000/reset-password?token=abc"
            , reset_token = "abc"
        )
        assert dispatched is True
        assert len(sent) == 1
    finally:
        EmailService.register_sender(None)


def test_r2_and_smtp_db_first_with_env_fallback(monkeypatch):
    # Reset caches
    R2ObjectService._cached_config    = None
    R2ObjectService._cache_expires_at = 0.0
    EmailService._cached_smtp         = None
    EmailService._cache_expires_at    = 0.0

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

    monkeypatch.setattr(
        EmailService
        , "_load_smtp_from_db"
        , classmethod(lambda cls: {
            "host"         : "smtp.db.local"
            , "port"       : 587
            , "user"       : "db_user"
            , "password"   : "db_pass"
            , "from_email" : "db@msm.local"
            , "use_tls"    : True
        })
    )
    smtp_cfg = EmailService.resolve_smtp_config()
    assert smtp_cfg["host"] == "smtp.db.local"
    assert smtp_cfg["from_email"] == "db@msm.local"

    # 2. Verify graceful fallback to .env when DB returns None
    R2ObjectService._cached_config    = None
    R2ObjectService._cache_expires_at = 0.0
    EmailService._cached_smtp         = None
    EmailService._cache_expires_at    = 0.0
    monkeypatch.setattr(R2ObjectService, "_load_config_from_db", classmethod(lambda cls: None))
    monkeypatch.setattr(EmailService, "_load_smtp_from_db", classmethod(lambda cls: None))

    assert R2ObjectService.resolve_config()["region"] == "auto"
    assert EmailService.resolve_smtp_config()["port"] == 587
