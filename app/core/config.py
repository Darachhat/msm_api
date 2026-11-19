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

    # JWT Auth
    JWT_SECRET_KEY                  : str = "change-me-to-a-strong-random-secret-key"
    JWT_ALGORITHM                   : str = "HS256"
    JWT_ACCESS_TOKEN_EXPIRE_MINUTES : int = 60
    JWT_REFRESH_TOKEN_EXPIRE_DAYS   : int = 7

    # Cloudflare R2
    R2_ACCOUNT_ID               : str = ""
    R2_ENDPOINT_URL             : str = ""
    R2_ACCESS_KEY_ID            : str = ""
    R2_SECRET_ACCESS_KEY        : str = ""
    R2_BUCKET_NAME              : str = "medicine-stock-reports"
    R2_REGION                   : str = "auto"
    R2_PUBLIC_URL               : str = ""
    R2_PRESIGNED_EXPIRE_SECONDS : int = 3600

    # CORS
    WHITE_LIST_CORS : List[str] = ["*"]


settings = Settings()
