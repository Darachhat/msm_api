from typing            import List
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file            = ".env"
        , env_file_encoding = "utf-8"
        , extra             = "ignore"
    )

    PROJECT_NAME : str = "Medicine Stock Management API"
    API_V1_STR   : str = "/api/v1"
    APP_BASE_URL : str = "http://localhost:8000"
    ENVIRONMENT  : str = "dev"

    # Database
    DB_DIALECT : str = "postgresql+psycopg"
    DB_HOST    : str = "localhost"
    DB_PORT    : str = "5432"
    DB_NAME    : str = "medicine_stock_db"
    DB_USER    : str = "postgres"
    DB_PASS    : str = "postgres"
    DB_SSL     : str = "disable"

    # JWT Auth (RS256 asymmetric keys via env)
    JWT_ALGORITHM                   : str = "RS256"
    JWT_PRIVATE_KEY                 : str = ""
    JWT_PUBLIC_KEY                  : str = ""
    JWT_ISSUER                      : str = "msm_api"
    JWT_AUDIENCE                    : str = "msm_client"
    JWT_ACCESS_TOKEN_EXPIRE_MINUTES : int = 15
    JWT_REFRESH_TOKEN_EXPIRE_DAYS   : int = 7

    # Hybrid Auth Cookies & CSRF
    COOKIE_REFRESH_NAME : str  = "msm_refresh_token"
    COOKIE_CSRF_NAME    : str  = "msm_csrf_token"
    COOKIE_SECURE       : bool = True
    COOKIE_SAMESITE     : str  = "lax"
    COOKIE_DOMAIN       : str  = ""
    COOKIE_REFRESH_PATH : str  = "/api/v1/auth"

    # Login Rate Limiting (In-memory sliding window)
    LOGIN_RATE_LIMIT_MAX_ATTEMPTS   : int = 5
    LOGIN_RATE_LIMIT_WINDOW_SECONDS : int = 300

    # Password Reset & SMTP
    PASSWORD_RESET_EXPIRE_MINUTES : int  = 30
    FRONTEND_RESET_PASSWORD_URL   : str  = "http://localhost:3000/reset-password"
    SMTP_HOST                     : str  = ""
    SMTP_PORT                     : int  = 587
    SMTP_USER                     : str  = ""
    SMTP_PASS                     : str  = ""
    SMTP_FROM                     : str  = "no-reply@msm.local"
    SMTP_USE_TLS                  : bool = True

    # Cloudflare R2
    R2_ACCOUNT_ID               : str = ""
    R2_ENDPOINT_URL             : str = ""
    R2_ACCESS_KEY_ID            : str = ""
    R2_SECRET_ACCESS_KEY        : str = ""
    R2_BUCKET_NAME              : str = "medicine-stock-reports"
    R2_REGION                   : str = "auto"
    R2_PUBLIC_URL               : str = ""
    R2_PRESIGNED_EXPIRE_SECONDS : int = 3600

    # CORS & Limits
    WHITE_LIST_CORS            : List[str] = ["*"]
    MAX_LOG_BODY_BYTES         : int       = 65536
    MAX_SIGNATURE_UPLOAD_BYTES : int       = 2 * 1024 * 1024


settings = Settings()
