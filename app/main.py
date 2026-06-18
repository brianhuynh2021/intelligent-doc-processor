from __future__ import annotations

from contextlib import asynccontextmanager
from time import monotonic
from uuid import uuid4

from a2a.server.events.in_memory_queue_manager import InMemoryQueueManager

# A2A
from a2a.server.request_handlers.default_request_handler import LegacyRequestHandler
from a2a.server.routes.agent_card_routes import create_agent_card_routes
from a2a.server.routes.jsonrpc_routes import create_jsonrpc_routes
from a2a.server.tasks.inmemory_task_store import InMemoryTaskStore
from a2a.types.a2a_pb2 import AgentCapabilities, AgentCard, AgentInterface, AgentSkill
from fastapi import APIRouter, FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from slowapi.middleware import SlowAPIMiddleware

from app.a2a_agent import DocProcessorAgentExecutor
from app.api.v1.routers.admin_router import router as admin_router
from app.api.v1.routers.api_keys_router import router as api_keys_router
from app.api.v1.routers.auth_router import router as auth_router
from app.api.v1.routers.chat_router import router as chat_router
from app.api.v1.routers.document_router import router as document_router
from app.api.v1.routers.files_router import router as files_router
from app.api.v1.routers.health_router import router as health_router
from app.api.v1.routers.search_router import router as search_router
from app.core.config import settings
from app.core.exception_handlers import register_exception_handlers
from app.core.logging import bind_context, clear_context, configure_logging, get_logger
from app.core.rate_limit import limiter

logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup/shutdown hooks. On shutdown, dispose the DB engine so in-flight
    connections are closed cleanly (graceful shutdown)."""
    logger.info("app_startup", environment=settings.ENVIRONMENT)
    yield
    from app.core.database import engine

    engine.dispose()
    logger.info("app_shutdown")


def create_app() -> FastAPI:
    configure_logging()

    app = FastAPI(
        title="Intelligent Document Processor",
        version=settings.VERSION,
        description=(
            "AI-powered document processing platform: upload → OCR → chunk → "
            "embed → semantic search & RAG chat. Auth via JWT or API key."
        ),
        lifespan=lifespan,
        openapi_tags=[
            {"name": "auth", "description": "Register, login, token refresh."},
            {"name": "files", "description": "Upload and manage raw files."},
            {
                "name": "documents",
                "description": "Document lifecycle: OCR, chunk, ingest, delete.",
            },
            {
                "name": "search",
                "description": "Semantic (vector) and keyword (full-text) search.",
            },
            {"name": "chat", "description": "RAG chat with conversation memory."},
            {
                "name": "api-keys",
                "description": "Programmatic access keys (X-API-Key).",
            },
            {"name": "admin", "description": "Admin-only stats and cache controls."},
            {
                "name": "Health",
                "description": "Liveness/readiness probes and dependency checks.",
            },
        ],
    )

    register_exception_handlers(app)
    app.state.limiter = limiter
    app.add_middleware(SlowAPIMiddleware)

    # Prometheus metrics at /metrics (request count, latency histograms, etc.)
    try:
        from prometheus_fastapi_instrumentator import Instrumentator

        Instrumentator(
            should_group_status_codes=True,
            excluded_handlers=["/metrics", "/health.*"],
        ).instrument(app).expose(app, endpoint="/metrics", include_in_schema=False)
    except ModuleNotFoundError:  # pragma: no cover
        logger.warning(
            "prometheus_fastapi_instrumentator not installed; /metrics disabled"
        )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.get_cors_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["*"],
    )

    @app.middleware("http")
    async def security_headers_middleware(request: Request, call_next):
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers[
            "Permissions-Policy"
        ] = "geolocation=(), microphone=(), camera=()"
        if settings.ENVIRONMENT == "production":
            response.headers[
                "Strict-Transport-Security"
            ] = "max-age=63072000; includeSubDomains"
        return response

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

    @app.get("/health")
    async def root_health_check():
        return {"status": "healthy"}

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
    api_v1.include_router(admin_router)
    api_v1.include_router(api_keys_router)
    app.include_router(api_v1)

    # ── A2A ──────────────────────────────────────────────────────────────
    _port = getattr(settings, "PORT", 8000)
    agent_card = AgentCard(
        name="Doc Processor Agent",
        description="Search documents and answer questions using RAG.",
        supported_interfaces=[AgentInterface(url=f"http://localhost:{_port}/a2a")],
        version="1.0.0",
        capabilities=AgentCapabilities(streaming=False),
        skills=[
            AgentSkill(
                id="ask_document",
                name="Ask Document",
                description="Answer questions from documents using RAG. Just type your question.",
                tags=["rag", "qa", "documents"],
            ),
            AgentSkill(
                id="search_documents",
                name="Search Documents",
                description="Semantic search. Prefix message with 'search:' e.g. 'search: invoices Q1'",
                tags=["search", "semantic", "documents"],
            ),
        ],
    )

    executor = DocProcessorAgentExecutor()
    task_store = InMemoryTaskStore()
    queue_manager = InMemoryQueueManager()

    handler = LegacyRequestHandler(
        agent_executor=executor,
        task_store=task_store,
        agent_card=agent_card,
        queue_manager=queue_manager,
    )

    for route in create_agent_card_routes(agent_card):
        app.router.routes.append(route)

    for route in create_jsonrpc_routes(handler, rpc_url="/a2a"):
        app.router.routes.append(route)
    # ─────────────────────────────────────────────────────────────────────

    return app


app = create_app()
