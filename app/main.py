from __future__ import annotations

from time import monotonic
from uuid import uuid4

from fastapi import APIRouter, FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1.routers.auth_router import router as auth_router
from app.api.v1.routers.chat_router import router as chat_router
from app.api.v1.routers.document_router import router as document_router
from app.api.v1.routers.files_router import router as files_router
from app.api.v1.routers.health_router import router as health_router
from app.api.v1.routers.search_router import router as search_router
from app.core.config import settings
from app.core.exception_handlers import register_exception_handlers
from app.core.logging import bind_context, clear_context, configure_logging, get_logger

logger = get_logger(__name__)


def create_app() -> FastAPI:
    configure_logging()

    app = FastAPI(
        title="Intelligent Document Processor",
        version=settings.VERSION,
        description="AI-powered document processing platform",
    )

    register_exception_handlers(app)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.middleware("http")
    async def request_context_middleware(request: Request, call_next):
        request_id = request.headers.get("X-Request-ID") or str(uuid4())
        request.state.request_id = request_id

        bind_context(request_id=request_id)
        start = monotonic()
        response = await call_next(request)
        duration_ms = int((monotonic() - start) * 1000)
        logger.info(
            "http_request",
            request_id=request_id,
            method=request.method,
            path=str(request.url.path),
            status_code=getattr(response, "status_code", None),
            duration_ms=duration_ms,
        )
        clear_context()

        response.headers.setdefault("X-Request-ID", request_id)
        return response

    api_v1 = APIRouter(prefix=settings.API_PREFIX)

    @app.get("/")
    def root():
        return {
            "message": "Welcome to Doc Processor API",
            "status": "running",
            "version": settings.VERSION,
        }

    @api_v1.get("/info")
    def info():
        return {
            "name": "Doc Processor API",
            "version": settings.VERSION,
            "feature": [
                "Document upload",
                "Text extraction",
                "AI processing",
                "Search & retrieval",
            ],
        }

    api_v1.include_router(auth_router)
    api_v1.include_router(files_router)
    api_v1.include_router(document_router)
    api_v1.include_router(health_router)
    api_v1.include_router(search_router)
    api_v1.include_router(chat_router)
    app.include_router(api_v1)

    return app


app = create_app()
