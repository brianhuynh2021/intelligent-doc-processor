from __future__ import annotations

import logging
from typing import Callable, TypeVar

import httpx
from tenacity import (
    before_sleep_log,
    retry,
    retry_if_exception,
    stop_after_attempt,
    wait_exponential,
)

from app.core.config import settings
from app.core.errors import AppError
from app.core.logging import get_logger

logger = get_logger(__name__)

T = TypeVar("T")


def _is_transient_exception(exc: BaseException) -> bool:
    if isinstance(exc, AppError):
        return False
    if isinstance(exc, (TimeoutError, OSError, ConnectionError, httpx.HTTPError)):
        return True

    status_code = getattr(exc, "status_code", None)
    if isinstance(status_code, int) and status_code in {408, 429, 500, 502, 503, 504}:
        return True

    # Optional: OpenAI SDK exception types (only present when openai is installed)
    try:  # pragma: no cover
        import openai

        transient = tuple(
            t
            for t in (
                getattr(openai, "RateLimitError", None),
                getattr(openai, "APIConnectionError", None),
                getattr(openai, "APITimeoutError", None),
                getattr(openai, "InternalServerError", None),
            )
            if t is not None
        )
        if transient and isinstance(exc, transient):
            return True
    except ModuleNotFoundError:  # pragma: no cover
        pass

    return False


def retry_transient(fn: Callable[..., T]) -> Callable[..., T]:
    return retry(
        reraise=True,
        retry=retry_if_exception(_is_transient_exception),
        stop=stop_after_attempt(settings.RETRY_MAX_ATTEMPTS),
        wait=wait_exponential(
            multiplier=settings.RETRY_MIN_BACKOFF_SECONDS,
            max=settings.RETRY_MAX_BACKOFF_SECONDS,
        ),
        before_sleep=before_sleep_log(logger, log_level=logging.WARNING),
    )(fn)
