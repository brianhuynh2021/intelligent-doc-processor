from __future__ import annotations

import contextvars
import json
import logging
import sys
from typing import Any

from app.core.config import settings

try:
    import structlog
except ModuleNotFoundError:  # pragma: no cover
    structlog = None  # type: ignore


_CONFIGURED = False
_CTX: contextvars.ContextVar[dict[str, Any]] = contextvars.ContextVar(
    "log_context", default={}
)


def configure_logging() -> None:
    global _CONFIGURED
    if _CONFIGURED:
        return

    log_level = (settings.LOG_LEVEL or "INFO").upper()
    logging.basicConfig(
        level=log_level,
        format="%(message)s",
        stream=sys.stdout,
    )

    if structlog is None:
        _CONFIGURED = True
        return

    processors: list[Any] = [
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso", utc=True),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
    ]

    if (settings.LOG_FORMAT or "json").lower() == "json":
        processors.append(structlog.processors.JSONRenderer())
    else:
        processors.append(structlog.dev.ConsoleRenderer())

    structlog.configure(
        processors=processors,
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )

    _CONFIGURED = True


def _merge_context(kwargs: dict[str, Any]) -> dict[str, Any]:
    ctx = dict(_CTX.get() or {})
    ctx.update(kwargs)
    return ctx


def _render_event(event: str, fields: dict[str, Any]) -> str:
    fmt = (settings.LOG_FORMAT or "json").lower()
    if fmt == "json":
        return json.dumps({"event": event, **fields}, default=str)
    if not fields:
        return event
    tail = " ".join(f"{k}={v}" for k, v in sorted(fields.items()))
    return f"{event} {tail}"


class _FallbackLogger:
    def __init__(self, base: logging.Logger):
        self._base = base

    def log(self, level: int, event: str, **kwargs: Any) -> None:
        fields = _merge_context(kwargs)
        self._base.log(level, _render_event(event, fields))

    def info(self, event: str, **kwargs: Any) -> None:
        self.log(logging.INFO, event, **kwargs)

    def warning(self, event: str, **kwargs: Any) -> None:
        self.log(logging.WARNING, event, **kwargs)

    def error(self, event: str, **kwargs: Any) -> None:
        self.log(logging.ERROR, event, **kwargs)

    def exception(self, event: str, **kwargs: Any) -> None:
        fields = _merge_context(kwargs)
        self._base.exception(_render_event(event, fields))


def get_logger(name: str | None = None):
    configure_logging()
    if structlog is None:
        return _FallbackLogger(logging.getLogger(name))
    return structlog.get_logger(name)


def bind_context(**kwargs: Any) -> None:
    if structlog is None:
        ctx = dict(_CTX.get() or {})
        ctx.update(kwargs)
        _CTX.set(ctx)
        return
    structlog.contextvars.bind_contextvars(**kwargs)


def clear_context() -> None:
    if structlog is None:
        _CTX.set({})
        return
    structlog.contextvars.clear_contextvars()
