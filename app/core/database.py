from typing import Generator

from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import NullPool  # noqa: F401

from app.core.config import app_config

engine = create_engine(
    app_config.get_db_url,
    echo=app_config.DEBUG,
    pool_pre_ping=True,
    pool_size=app_config.DATABASE_POOL_SIZE,
    max_overflow=app_config.DATABASE_MAX_OVERFLOW,
    pool_recycle=3600,
    # For production with pgbouncer, use NullPool:
    # poolclass=NullPool if app_config.ENVIRONMENT == "production" else None
)

# Create SessionLocal class

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db() -> Generator[Session, None, None]:
    """
    FastAPI dependency for database sessions.

    Yields:
        Session: SQLAlchemy database session

    Usage:
        @app.get("/items")
        def get_items(db: Session = Depends(get_db)):
            return db.query(Item).all()
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db() -> None:
    """
    Initialize database - create all tables.

    Note: In production, use Alembic migrations instead.
    This is mainly for testing/development.
    """
    from app.models.base import Base
    from app.models.chunk_model import Chunk  # noqa: F401
    from app.models.document_model import Document  # noqa: F401
    from app.models.user_model import User  # noqa: F401

    Base.metadata.create_all(bind=engine)
    print("✅ Database tables created successfully!")


def drop_db() -> None:
    """
    Drop all tables - USE WITH CAUTION!

    Only for development/testing.
    """
    from app.models.base import Base

    Base.metadata.drop_all(bind=engine)
    print("⚠️  All database tables dropped!")


# Health check function
def check_db_connection() -> bool:
    """
    Check if database connection is working.

    Returns:
        bool: True if connection is successful
    """
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return True
    except Exception as e:
        print(f"❌ Database connection failed: {e}")
        return False
