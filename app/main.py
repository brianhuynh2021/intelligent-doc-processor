from fastapi import APIRouter, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

from app.api.v1.routers.auth_router import router as auth_router
from app.api.v1.routers.chat_router import router as chat_router
from app.api.v1.routers.document_router import router as document_router
from app.api.v1.routers.files_router import router as files_router
from app.api.v1.routers.health_router import router as health_router
from app.api.v1.routers.search_router import router as search_router

app = FastAPI(
    title="Intelligent Document Processor",
    version="0.1.0",
    description="AI-powered document processing platform",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

api_v1 = APIRouter(prefix="/api/v1")


@app.get("/")
def root():
    return {
        "message": "Welcome to Doc Processor API",
        "status": "running",
        "version": "0.1.0",
    }


@api_v1.get("/info")
def info():
    return {
        "name": "Doc Processor API",
        "version": "0.1.0",
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
