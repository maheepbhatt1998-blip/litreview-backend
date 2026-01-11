from pydantic_settings import BaseSettings
from typing import Optional, List
import os


class Settings(BaseSettings):
    # Application
    APP_NAME: str = "Literature Review Assistant"
    DEBUG: bool = False

    # Database - defaults to SQLite for local, set DATABASE_URL env var for PostgreSQL
    DATABASE_URL: str = "sqlite+aiosqlite:///./litreview.db"

    # Redis (optional for local development)
    REDIS_URL: str = "redis://localhost:6379/0"

    # JWT Authentication
    SECRET_KEY: str = "your-super-secret-key-change-in-production"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 7  # 7 days

    # Claude API
    ANTHROPIC_API_KEY: Optional[str] = None
    CLAUDE_MODEL: str = "claude-sonnet-4-20250514"

    # Semantic Scholar API
    SEMANTIC_SCHOLAR_API_KEY: Optional[str] = None

    # File Storage
    UPLOAD_DIR: str = "./uploads"
    MAX_FILE_SIZE: int = 50 * 1024 * 1024  # 50MB

    # CORS - add your Vercel domain here
    CORS_ORIGINS: List[str] = [
        "http://localhost:3000",
        "https://*.vercel.app",
    ]

    class Config:
        env_file = ".env"
        case_sensitive = True

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        # Convert PostgreSQL URL format for asyncpg if needed
        if self.DATABASE_URL.startswith("postgres://"):
            self.DATABASE_URL = self.DATABASE_URL.replace("postgres://", "postgresql+asyncpg://", 1)
        elif self.DATABASE_URL.startswith("postgresql://") and "+asyncpg" not in self.DATABASE_URL:
            self.DATABASE_URL = self.DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://", 1)


settings = Settings()

# Create upload directory if it doesn't exist
os.makedirs(settings.UPLOAD_DIR, exist_ok=True)
