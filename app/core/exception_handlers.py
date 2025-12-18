from __future__ import annotations

import traceback
from typing import Any
from uuid import uuid4

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from starlette.responses import JSONResponse

from app.core.config import settings
from app.core.errors import AppError
from app.core.logging import get_logger
from app.schemas.error_schema import ErrorEnvelope, ErrorResponse, ValidationErrorItem

logger = get_logger(__name__)


def _status_code_to_code(status_code: int) -> str:
    return {
        400: "bad_request",
        401: "unauthorized",
        403: "forbidden",
        404: "not_found",
        409: "conflict",
        422: "validation_error",
        429: "rate_limited",
        500: "internal_error",
        502: "upstream_error",
        503: "service_unavailable",
    }.get(status_code, "http_error")


def _get_request_id(request: Request) -> str:
    rid = getattr(request.state, "request_id", None)
    if rid:
        return str(rid)
    incoming = request.headers.get("X-Request-ID")
    if incoming:
        return incoming
    return str(uuid4())


def _error_response(
    *,
    request: Request,
    status_code: int,
    code: str,
    message: str,
    details: list[Any] | None = None,
):
    payload = ErrorResponse(
        request_id=_get_request_id(request),
        error=ErrorEnvelope(code=code, message=message, details=details),
    )
    return JSONResponse(
        status_code=status_code,
        content=payload.model_dump(mode="json", exclude_none=True),
        headers={"X-Request-ID": payload.request_id},
    )


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(RequestValidationError)
    async def request_validation_error_handler(
        request: Request, exc: RequestValidationError
    ):
        details = [
            ValidationErrorItem(
                type=e.get("type"),
                loc=list(e.get("loc") or []),
                msg=str(e.get("msg") or "Invalid value"),
                input=e.get("input"),
            ).model_dump(mode="json", exclude_none=True)
            for e in exc.errors()
        ]
        return _error_response(
            request=request,
            status_code=422,
            code="validation_error",
            message="Request validation failed",
            details=details,
        )

    @app.exception_handler(AppError)
    async def app_error_handler(request: Request, exc: AppError):
        return _error_response(
            request=request,
            status_code=exc.status_code,
            code=exc.code,
            message=exc.message,
            details=exc.details,
        )

    @app.exception_handler(HTTPException)
    async def http_exception_handler(request: Request, exc: HTTPException):
        code = _status_code_to_code(int(exc.status_code))
        message = "Request failed"
        details: list[Any] | None = None

        if isinstance(exc.detail, dict):
            code = str(exc.detail.get("code") or code)
            message = str(
                exc.detail.get("message")
                or exc.detail.get("detail")
                or exc.detail.get("error")
                or message
            )
            details = exc.detail.get("details")
        else:
            message = str(exc.detail)

        return _error_response(
            request=request,
            status_code=int(exc.status_code),
            code=code,
            message=message,
            details=details,
        )

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(request: Request, exc: Exception):
        request_id = _get_request_id(request)
        logger.error(
            "unhandled_exception",
            request_id=request_id,
            path=str(request.url.path),
            method=request.method,
            traceback="".join(
                traceback.format_exception(type(exc), exc, exc.__traceback__)
            ),
        )

        message = str(exc) if settings.DEBUG else "Internal server error"
        details = [{"type": type(exc).__name__}] if settings.DEBUG else None
        return _error_response(
            request=request,
            status_code=500,
            code="internal_error",
            message=message,
            details=details,
        )
