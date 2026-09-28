"""Domain errors and the single place they become HTTP responses.

Services raise these; route handlers never catch them. That keeps routes thin and
means a 402 or a 404 looks the same on every endpoint.
"""

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse


class DomainError(Exception):
    status_code = 400
    detail = "request could not be processed"


class NotFound(DomainError):
    # Also used when a record exists in another workspace. Saying "not yours"
    # would confirm the id is real, so the caller only ever hears "not found".
    status_code = 404
    detail = "not found"


class OutOfCredits(DomainError):
    status_code = 402
    detail = "workspace is out of AI credits"


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(DomainError)
    async def _domain_error(_: Request, exc: DomainError) -> JSONResponse:
        return JSONResponse({"detail": exc.detail}, status_code=exc.status_code)
