import os
from pathlib import Path

from pydantic_settings import BaseSettings

BASE_DIR = Path(__file__).resolve().parent.parent.parent
UPLOAD_DIR = BASE_DIR / "uploads"

UPLOAD_DIR.mkdir(parents=True, exist_ok=True)


TESSERACT_CMD = os.getenv("TESSERACT_CMD", "/opt/homebrew/bin/tesseract")
POPPLER_PATH = os.getenv("POPPLER_PATH", "/opt/homebrew/opt/poppler/bin")

ALLOWED_CONTENT_TYPES = {
    # PDF
    "application/pdf",
    # DOCX
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    # Images
    "image/png",
    "image/jpeg",
    # CSV
    "text/csv",
    "application/vnd.ms-excel",  # một số browser gửi CSV kiểu này
    # TXT
    "text/plain",
}

MAX_FILE_SIZE = 10 * 1024 * 1024  # 10 MB


class AppSettings(BaseSettings):
    """Application settings"""

    # Vector DB Settings
    QDRANT_URL: str = os.getenv("QDRANT_URL", "http://localhost:6333")
    QDRANT_COLLECTION: str = os.getenv("QDRANT_COLLECTION", "documents")
    EMBEDDING_DIM: int = int(os.getenv("EMBEDDING_DIM", "1536"))
    QDRANT_API_KEY: str | None = os.getenv("QDRANT_API_KEY")  # optional

    # Project
    PROJECT_NAME: str = os.getenv("APP_NAME", "Intelligent Doc Processor")
    VERSION: str = os.getenv("APP_VERSION", "0.1.0")
    API_PREFIX: str = os.getenv("API_V1_PREFIX", "/api/v1")
    ENVIRONMENT: str = os.getenv("APP_ENV", "development")
    DEBUG: bool = os.getenv("DEBUG", "true").lower() == "true"
    HOST: str = os.getenv("HOST", "0.0.0.0")
    PORT: int = int(os.getenv("PORT", "8000"))
    # Database
    DATABASE_URL: str = os.getenv(
        "DATABASE_URL",
        "postgresql+asyncpg://postgres:postgres@localhost:5433/intelligent_docs",
    )
    DATABASE_POOL_SIZE: int = int(os.getenv("DATABASE_POOL_SIZE", "5"))
    DATABASE_MAX_OVERFLOW: int = int(os.getenv("DATABASE_MAX_OVERFLOW", "10"))

    @property
    def get_db_url(self) -> str:
        """Build database URL"""
        return self.DATABASE_URL.replace("+asyncpg", "")

    # Cache Redis
    CACHE_HOST: str = os.getenv("REDIS_HOST", "localhost")
    CACHE_PORT: int = int(os.getenv("REDIS_PORT", "6379"))
    CACHE_PASSWORD: str = os.getenv("REDIS_PASSWORD", "")

    @property
    def get_cache_url(self) -> str:
        """Build cache URL"""
        if self.CACHE_PASSWORD:
            return (
                f"redis://:{self.CACHE_PASSWORD}@{self.CACHE_HOST}:{self.CACHE_PORT}/0"
            )
        return f"redis://{self.CACHE_HOST}:{self.CACHE_PORT}/0"

    # Security
    JWT_SECRET_KEY: str = os.getenv("JWT_SECRET_KEY", "dev-secret-change-in-prod")
    JWT_ALGORITHM: str = os.getenv("JWT_ALGORITHM", "HS256")
    ACCESS_TOKEN_EXPIRE_MINUTES: int = int(
        os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "30")
    )

    # File Upload
    UPLOAD_DIR: str = os.getenv("UPLOAD_DIR", "./uploads")
    MAX_UPLOAD_SIZE: int = int(os.getenv("MAX_UPLOAD_SIZE", "10485760"))
    ALLOWED_EXTENSIONS: str = os.getenv(
        "ALLOWED_EXTENSIONS", "pdf,png,jpg,jpeg,txt,docx"
    )

    @property
    def get_allowed_extensions(self) -> list[str]:
        """Get allowed file extensions as list"""
        return self.ALLOWED_EXTENSIONS.split(",")

    @property
    def get_upload_path(self) -> str:
        """Get upload directory path"""
        return self.UPLOAD_DIR

    # AI/ML Settings
    OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "your-openai-api-key-here")
    EMBEDDING_MODEL: str = os.getenv("EMBEDDING_MODEL", "text-embedding-3-small")
    LLM_MODEL: str = os.getenv("LLM_MODEL", "gpt-4")
    ANTHROPIC_API_KEY: str | None = os.getenv("ANTHROPIC_API_KEY")
    GEMINI_API_KEY: str | None = os.getenv("GEMINI_API_KEY") or os.getenv(
        "GOOGLE_API_KEY"
    )
    MAX_TOKENS: int = int(os.getenv("MAX_TOKENS", "4096"))

    # Vector Database (Add these from .env)
    VECTOR_DB_PATH: str = os.getenv("VECTOR_DB_PATH", "./data/vector_db")
    VECTOR_COLLECTION_NAME: str = os.getenv("VECTOR_COLLECTION_NAME", "documents")

    # Logging (Add these from .env)
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")
    LOG_FORMAT: str = os.getenv("LOG_FORMAT", "json")

    # Retries
    RETRY_MAX_ATTEMPTS: int = int(os.getenv("RETRY_MAX_ATTEMPTS", "3"))
    RETRY_MIN_BACKOFF_SECONDS: float = float(
        os.getenv("RETRY_MIN_BACKOFF_SECONDS", "0.5")
    )
    RETRY_MAX_BACKOFF_SECONDS: float = float(
        os.getenv("RETRY_MAX_BACKOFF_SECONDS", "8")
    )

    REFRESH_TOKEN_EXPIRE_DAYS: int = 14
    REFRESH_COOKIE_NAME: str = "rt"
    REFRESH_COOKIE_SECURE: bool = True
    REFRESH_COOKIE_SAMESITE: str = "lax"

    # Cache Settings
    REDIS_URL: str = os.getenv("REDIS_URL", "redis://localhost:6379/0")

    class Config:
        env_file = ".env"
        case_sensitive = True
        extra = "ignore"


settings = AppSettings()
