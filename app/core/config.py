from pydantic_settings import BaseSettings


class AppSettings(BaseSettings):
    """Application settings"""

    # Project
    PROJECT_NAME: str = "Intelligent Doc Processor"
    VERSION: str = "0.1.0"
    API_PREFIX: str = "/api/v1"

    # Database
    DB_USER: str = "postgres"
    DB_PASS: str = "postgres"
    DB_NAME: str = "doc_processor"
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

    # Cache
    CACHE_HOST: str = "redis"
    CACHE_PORT: int = 6379

    @property
    def get_cache_url(self) -> str:
        """Build cache URL"""
        return f"redis://{self.CACHE_HOST}:{self.CACHE_PORT}/0"

    # Security
    SECRET_KEY: str = "dev-secret-change-in-prod"
    HASH_ALGORITHM: str = "HS256"
    TOKEN_LIFETIME: int = 30

    # Upload
    UPLOAD_PATH: str = "./uploads"
    MAX_FILE_SIZE: int = 10 * 1024 * 1024  # 10MB

    class Config:
        case_sensitive = True


app_config = AppSettings()
