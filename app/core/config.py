import os

from pydantic_settings import BaseSettings


class AppSettings(BaseSettings):
    """Application settings"""

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
        "postgresql+asyncpg://postgres:postgres@localhost:5432/intelligent_docs",
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
    SECRET_KEY: str = os.getenv("SECRET_KEY", "dev-secret-change-in-prod")
    ALGORITHM: str = os.getenv("ALGORITHM", "HS256")
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
    MAX_TOKENS: int = int(os.getenv("MAX_TOKENS", "4096"))

    # Vector Database (Add these from .env)
    VECTOR_DB_PATH: str = os.getenv("VECTOR_DB_PATH", "./data/vector_db")
    VECTOR_COLLECTION_NAME: str = os.getenv("VECTOR_COLLECTION_NAME", "documents")

    # Logging (Add these from .env)
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")
    LOG_FORMAT: str = os.getenv("LOG_FORMAT", "json")

    class Config:
        env_file = ".env"
        case_sensitive = True
        extra = "ignore"


app_config = AppSettings()
