# ruff : noqa: E402
"""Test database connection and engine"""
import sys
from pathlib import Path

# Add project root to Python path
project_root = Path(__file__).parent.parent  # noqa: 401
sys.path.insert(0, str(project_root))  # noqa: 401

from typing import Any, Optional

from sqlalchemy import text

from app.core.config import app_config
from app.core.database import SessionLocal, check_db_connection, engine
from app.models.chunk_model import Chunk
from app.models.document_model import Document
from app.models.user_model import User


def execute_query(conn, query: str) -> Optional[Any]:
    """
    Execute query and return first column of first row.

    Args:
        conn: Database connection
        query: SQL query string

    Returns:
        First column value or None
    """
    result = conn.execute(text(query))
    row = result.fetchone()
    return row[0] if row else None


def test_engine_connection():
    """Test engine connection"""
    print("🧪 Testing Engine Connection...\n")

    try:
        with engine.connect() as conn:
            # PostgreSQL version
            version = execute_query(conn, "SELECT version();")
            if version:
                print(f"✅ PostgreSQL Version: {version}\n")

            # Database name
            db_name = execute_query(conn, "SELECT current_database();")
            if db_name:
                print(f"✅ Connected to database: {db_name}\n")

            # Current user
            user = execute_query(conn, "SELECT current_user;")
            if user:
                print(f"✅ Connected as user: {user}\n")

        return True
    except Exception as e:
        print(f"❌ Engine connection failed: {e}\n")
        return False


def test_session():
    """Test session creation"""
    print("🧪 Testing Session Creation...\n")

    try:
        db = SessionLocal()

        value = execute_query(db, "SELECT 1 + 1 as result;")
        if value:
            print(f"✅ Session query result: {value}\n")

        db.close()
        return True
    except Exception as e:
        print(f"❌ Session test failed: {e}\n")
        return False


def test_models_loaded():
    """Test that models are loaded"""
    print("🧪 Testing Models...\n")

    try:
        models = [("User", User), ("Document", Document), ("Chunk", Chunk)]

        for name, model in models:
            print(f"✅ {name} table: {model.__tablename__}")

        print("\n📋 Chunk columns:")
        for col in Chunk.__table__.columns:
            print(f"   - {col.name}: {col.type}")

        print()
        return True
    except Exception as e:
        print(f"❌ Models test failed: {e}\n")
        return False


def test_connection_pool():
    """Test connection pool stats"""
    print("🧪 Testing Connection Pool...\n")

    try:
        pool = engine.pool

        # Get pool information
        print(f"✅ Pool Type: {pool.__class__.__name__}")
        print(f"✅ Pool Status: {pool.status()}")

        # Test that pool can create connections
        with engine.connect() as conn:
            result = conn.execute(text("SELECT 1"))
            print(f"✅ Pool connection test: {result.scalar()}")

        print()
        return True
    except Exception as e:
        print(f"❌ Pool test failed: {e}\n")
        return False


def print_header():
    """Print test header"""
    print("=" * 60)
    print("🚀 DATABASE ENGINE TEST")
    print("=" * 60)
    print()


def print_config():
    """Print database configuration"""
    # ✅ FIXED: Use fields that actually exist in your config
    config_items = [
        ("Project", app_config.PROJECT_NAME),
        ("Version", app_config.VERSION),
        ("Environment", app_config.ENVIRONMENT),
        ("Database URL", f"{app_config.get_db_url[:60]}..."),
        ("Debug Mode", app_config.DEBUG),
    ]

    for label, value in config_items:
        print(f"📊 {label}: {value}")
    print()


def run_connection_check():
    """Check initial connection"""
    print("🔌 Checking connection...")
    if check_db_connection():
        print("✅ Database connection successful!\n")
        return True
    else:
        print("❌ Database connection failed!")
        print("💡 Make sure:")
        print("   1. PostgreSQL is running")
        print("   2. Database exists (check DATABASE_URL in .env)")
        print("   3. Credentials are correct")
        print()
        return False


def run_tests():
    """Run all tests and return results"""
    tests = [
        ("Engine Connection", test_engine_connection),
        ("Session Creation", test_session),
        ("Models Loaded", test_models_loaded),
        ("Connection Pool", test_connection_pool),
    ]

    results = []
    for name, test_func in tests:
        result = test_func()
        results.append((name, result))

    return results


def print_results(results):
    """Print test results"""
    print("=" * 60)
    print("📊 TEST RESULTS")
    print("=" * 60)

    for name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status} - {name}")

    print("=" * 60)


def print_next_steps(all_passed: bool):
    """Print next steps"""
    if all_passed:
        print("\n🎉 All tests passed! Database engine is ready!")
        print("\n📝 Next steps:")
        next_steps = [
            "Create migration: alembic revision --autogenerate -m 'Add models'",
            "Apply migration: alembic upgrade head",
            "Start building API endpoints",
        ]
        for i, step in enumerate(next_steps, 1):
            print(f"   {i}. {step}")
        print()
    else:
        print("\n❌ Some tests failed. Check errors above.\n")


def main():
    """Run all tests"""
    print_header()
    print_config()

    # Connection check
    if not run_connection_check():
        return

    # Run all tests
    results = run_tests()

    # Show results
    print_results(results)

    # Next steps
    all_passed = all(result for _, result in results)
    print_next_steps(all_passed)


if __name__ == "__main__":
    main()
