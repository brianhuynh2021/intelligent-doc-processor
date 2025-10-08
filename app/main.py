from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

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


@app.get("/")
def root():
    return {
        "message": "Welcome to Doc Processor API",
        "status": "running",
        "version": "0.1.0",
    }


@app.get("/health")
def health():
    return {
        "status": "healthy",
        "database": "not connected yet",
        "redis": "not connected yet",
    }


@app.get("/api/v1/info")
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
