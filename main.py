import traceback
from contextlib import asynccontextmanager
from typing     import AsyncGenerator
from uuid       import uuid4

from fastapi                 import FastAPI, Request
from fastapi.exceptions      import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from starlette.exceptions    import HTTPException as StarletteHTTPException

from app.api.v1.router     import router as v1_router
from app.core.config       import settings
from app.core.httpx_client import create_httpx_client, set_global_httpx_client
from app.core.log          import logger
from app.middleware        import AuthMiddleware, LogMiddleware, TraceMiddleware

process_id = uuid4()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    logger.info(f"Process started... {process_id}")

    httpx_client           = create_httpx_client()
    app.state.httpx_client = httpx_client
    set_global_httpx_client(httpx_client)

    try:
        yield
    finally:
        set_global_httpx_client(None)
        app.state.httpx_client = None
        try:
            await httpx_client.aclose()
        except Exception:
            logger.error(f"Error closing httpx client\n{traceback.format_exc()}")

        logger.info(f"Process stopped... {process_id}")


app = FastAPI(
    title         = settings.PROJECT_NAME
    , openapi_url = f"{settings.API_V1_STR}/openapi.json"
    , lifespan    = lifespan
)

# Request flow:  TraceMiddleware → CORS → AuthMiddleware → LogMiddleware (inbound system_log) → Route
# Response flow: Route → LogMiddleware → AuthMiddleware → CORS → TraceMiddleware
app.middleware("http")(LogMiddleware.log_access)
app.add_middleware(AuthMiddleware)
app.add_middleware(
    CORSMiddleware
    , allow_origins     = settings.WHITE_LIST_CORS
    , allow_credentials = True
    , allow_methods     = ["*"]
    , allow_headers     = ["*"]
)
app.add_middleware(TraceMiddleware)


@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(request: Request, exception: StarletteHTTPException):
    return await LogMiddleware.http_exception(request=request, exception=exception)


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exception: RequestValidationError):
    return await LogMiddleware.validation_exception(request=request, exception=exception)


@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exception: Exception):
    """Catch all unhandled exceptions and log with full traceback."""
    return await LogMiddleware.unhandled_exception(request=request, exception=exception)


app.include_router(v1_router, prefix = settings.API_V1_STR)


@app.get("/health", tags = ["Health"])
def health():
    return {
        "status"    : "ok"
        , "service" : settings.PROJECT_NAME
    }
