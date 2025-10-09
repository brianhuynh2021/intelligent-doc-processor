import os

from pydantic_settings import BaseSettings


class AppSettings(BaseSettings):
    """Application settings"""

    # Project
    PROJECT_NAME: str = "Intelligent Doc Processor"
    VERSION: str = "0.1.0"
    API_PREFIX: str = "/api/v1"
    ENVIRONMENT: str = os.getenv("APP_ENV", "development")
    DEBUG: bool = os.getenv("DEBUG", "true").lower() == "true"

    # Database
    DB_USER: str = os.getenv("POSTGRES_USER", "postgres")
    DB_PASS: str = os.getenv("POSTGRES_PASSWORD", "postgres")
    DB_NAME: str = os.getenv("POSTGRES_DB", "doc_processor")
    DB_HOST: str = "db"
    DB_PORT: int = 5432

    @property
    def get_db_url(self) -> str:
        """Build database URL"""
        return (
            f"postgresql+psycopg2://{self.DB_USER}:"
            f"{self.DB_PASS}@{self.DB_HOST}:"
            f"{self.DB_PORT}/{self.DB_NAME}"
        )

    # Cache Redis
    CACHE_HOST: str = "redis"
    CACHE_PORT: int = 6379
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
    HASH_ALGORITHM: str = "HS256"
    TOKEN_LIFETIME: int = 30

    # Upload
    UPLOAD_PATH: str = "./uploads"
    MAX_FILE_SIZE: int = 10 * 1024 * 1024  # 10MB

    class Config:
        case_sensitive = True


app_config = AppSettings()
