import traceback
from time import perf_counter

from fastapi                    import Request, Response, status
from fastapi.exception_handlers import request_validation_exception_handler
from fastapi.exceptions         import RequestValidationError
from fastapi.responses          import JSONResponse
from starlette.exceptions       import HTTPException

from app.core.log import logger


class LogMiddleware:

    @staticmethod
    async def log_access(request: Request, call_next) -> Response:
        """Write one app.log line per request: method, path, status and duration."""
        start_time = perf_counter()
        response   = await call_next(request)
        duration   = round((perf_counter() - start_time) * 1000, 2)
        client_ip  = request.client.host if request.client else 'N/A'

        message = f'{request.method} {request.url.path} {response.status_code} {duration}ms ip: {client_ip}'
        if response.status_code >= status.HTTP_500_INTERNAL_SERVER_ERROR:
            logger.error(message)
        elif response.status_code >= status.HTTP_400_BAD_REQUEST:
            logger.warn(message)
        else:
            logger.info(message)
        return response


    @staticmethod
    async def unhandled_exception(request: Request, exception: Exception) -> JSONResponse:
        """Log unhandled exceptions with the full traceback and return a generic 500."""
        logger.error(
            f'Unhandled exception in {request.method} {request.url.path}'
            , f'- {type(exception).__name__}: {exception}'
            , f'traceback: {"".join(traceback.format_exception(exception))}'
        )
        return JSONResponse(
            status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
            , content   = {'detail': 'Internal server error'}
        )


    @staticmethod
    async def validation_exception(request: Request, exception: RequestValidationError) -> JSONResponse:
        logger.warn(f'Validation error in {request.method} {request.url.path} - {exception.errors()}')
        return await request_validation_exception_handler(request, exception)


    @staticmethod
    async def http_exception(request: Request, exception: HTTPException) -> JSONResponse:
        log_method = logger.error if exception.status_code >= status.HTTP_500_INTERNAL_SERVER_ERROR else logger.warn
        log_method(f'HTTPException {exception.status_code} in {request.method} {request.url.path} - {exception.detail}')
        return JSONResponse(
            status_code = exception.status_code
            , content   = {'detail': exception.detail}
            , headers   = getattr(exception, 'headers', None)
        )
