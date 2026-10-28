from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse


class DocSentryError(Exception):
    status_code = 500
    code = "internal_error"

    def __init__(self, message: str = "Internal error") -> None:
        super().__init__(message)
        self.message = message


class AuthError(DocSentryError):
    status_code, code = 401, "unauthorized"


class ForbiddenError(DocSentryError):
    status_code, code = 403, "forbidden"


class NotFoundError(DocSentryError):
    status_code, code = 404, "not_found"


class InvalidInputError(DocSentryError):
    status_code, code = 422, "invalid_input"


class PasswordRequiredError(InvalidInputError):
    code = "password_required"


class ProcessingError(DocSentryError):
    status_code, code = 500, "processing_failed"


class LockedError(DocSentryError):
    status_code, code = 423, "locked"


def install_handlers(app: FastAPI) -> None:
    @app.exception_handler(DocSentryError)
    async def _handle(_: Request, exc: DocSentryError) -> JSONResponse:
        return JSONResponse(status_code=exc.status_code,
                            content={"error": {"code": exc.code, "message": exc.message}})

    @app.exception_handler(Exception)
    async def _unexpected(_: Request, exc: Exception) -> JSONResponse:
        return JSONResponse(status_code=500,
                            content={"error": {"code": "internal_error", "message": "Unexpected error"}})