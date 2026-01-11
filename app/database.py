from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy import text
from app.config import settings


# Determine if using SQLite
is_sqlite = settings.DATABASE_URL.startswith("sqlite")

# Create async engine with appropriate settings
if is_sqlite:
    engine = create_async_engine(
        settings.DATABASE_URL,
        echo=settings.DEBUG,
        connect_args={"check_same_thread": False},
    )
else:
    engine = create_async_engine(
        settings.DATABASE_URL,
        echo=settings.DEBUG,
        pool_pre_ping=True,
        pool_size=10,
        max_overflow=20,
    )

# Create async session factory
AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)


# Base class for models
class Base(DeclarativeBase):
    pass


# Dependency to get database session
async def get_db():
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()


# Initialize database (create tables and extensions)
async def init_db():
    async with engine.begin() as conn:
        # Enable pgvector extension only for PostgreSQL
        if not is_sqlite:
            try:
                await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
            except Exception:
                pass  # Extension might not be available
        # Create all tables
        await conn.run_sync(Base.metadata.create_all)


# Close database connections
async def close_db():
    await engine.dispose()
