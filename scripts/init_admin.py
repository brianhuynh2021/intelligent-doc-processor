"""Create default admin user if not exists."""

import asyncio
import os
import sys

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker


def _resolve_password_hasher():
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if project_root not in sys.path:
        sys.path.insert(0, project_root)

    from app.core.security import get_password_hash

    return get_password_hash


async def create_admin():
    admin_username = os.getenv("DEFAULT_ADMIN_USERNAME", "admin")
    admin_email = os.getenv("DEFAULT_ADMIN_EMAIL", "admin@admin.com")
    admin_password = os.getenv("DEFAULT_ADMIN_PASSWORD", "12345678")

    database_url = os.getenv(
        "DATABASE_URL",
        "postgresql+asyncpg://postgres:postgres@db:5432/intelligent_docs",
    )
    engine = create_async_engine(database_url)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with async_session() as session:
        # Check if admin already exists
        result = await session.execute(
            text("SELECT id FROM users WHERE username = :username OR email = :email"),
            {"username": admin_username, "email": admin_email},
        )
        if result.fetchone():
            print("[init_admin] Admin user already exists, skipping.")
            await engine.dispose()
            return

        get_password_hash = _resolve_password_hasher()
        hashed = get_password_hash(admin_password)

        await session.execute(
            text(
                """
                INSERT INTO users (
                    username,
                    email,
                    hashed_password,
                    is_active,
                    is_admin,
                    is_deleted,
                    login_count
                )
                VALUES (:username, :email, :hashed_password, true, true, false, 0)
                ON CONFLICT (username) DO NOTHING
                """
            ),
            {
                "username": admin_username,
                "email": admin_email,
                "hashed_password": hashed,
            },
        )
        await session.commit()
        print(f"[init_admin] Admin user created: {admin_username} / {admin_password}")

    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(create_admin())
