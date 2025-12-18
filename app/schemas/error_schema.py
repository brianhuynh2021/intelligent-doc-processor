from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


class ValidationErrorItem(BaseModel):
    type: str | None = None
    loc: list[str | int] = Field(default_factory=list)
    msg: str
    input: Any | None = None


class ErrorEnvelope(BaseModel):
    code: str
    message: str
    details: list[Any] | None = None


class ErrorResponse(BaseModel):
    error: ErrorEnvelope
    request_id: str
    success: Literal[False] = False
