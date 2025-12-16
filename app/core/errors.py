from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(slots=True)
class AppError(Exception):
    status_code: int
    code: str
    message: str
    details: list[Any] | None = None


class NotFoundError(AppError):
    def __init__(self, message: str = "Not found", *, details: list[Any] | None = None):
        super().__init__(
            status_code=404, code="not_found", message=message, details=details
        )


class ConflictError(AppError):
    def __init__(self, message: str = "Conflict", *, details: list[Any] | None = None):
        super().__init__(
            status_code=409, code="conflict", message=message, details=details
        )


class BadRequestError(AppError):
    def __init__(
        self, message: str = "Bad request", *, details: list[Any] | None = None
    ):
        super().__init__(
            status_code=400, code="bad_request", message=message, details=details
        )


class UnauthorizedError(AppError):
    def __init__(
        self, message: str = "Unauthorized", *, details: list[Any] | None = None
    ):
        super().__init__(
            status_code=401, code="unauthorized", message=message, details=details
        )


class ForbiddenError(AppError):
    def __init__(self, message: str = "Forbidden", *, details: list[Any] | None = None):
        super().__init__(
            status_code=403, code="forbidden", message=message, details=details
        )


class UpstreamServiceError(AppError):
    def __init__(
        self,
        message: str = "Upstream service error",
        *,
        details: list[Any] | None = None,
    ):
        super().__init__(
            status_code=502, code="upstream_error", message=message, details=details
        )


class DependencyMissingError(AppError):
    def __init__(
        self,
        message: str = "Optional dependency is not installed",
        *,
        details: list[Any] | None = None,
    ):
        super().__init__(
            status_code=503, code="dependency_missing", message=message, details=details
        )
