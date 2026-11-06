"""
Namma Civic — Application Configuration
Reads from .env file via pydantic-settings.
"""
from __future__ import annotations

from enum import Enum
from functools import lru_cache
import os
from typing import List

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class AppEnv(str, Enum):
    development = "development"
    production = "production"
    test = "test"


class DatabaseMode(str, Enum):
    sqlite = "sqlite"
    postgresql = "postgresql"


class AIMode(str, Enum):
    mock = "mock"
    groq = "groq"
    openai = "openai"
    gemini = "gemini"


class MCPMode(str, Enum):
    mock = "mock"
    local = "local"
    remote = "remote"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ── Application ──────────────────────────────────────────
    app_env: AppEnv = AppEnv.development
    app_name: str = "Namma Civic"
    app_version: str = "1.0.0"
    debug: bool = True

    # ── Database ─────────────────────────────────────────────
    database_url: str = "sqlite:///./namma-civic.db"
    database_mode: DatabaseMode = DatabaseMode.sqlite

    # ── Security ─────────────────────────────────────────────
    jwt_secret: str = "CHANGE_ME_IN_PRODUCTION"
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 60

    # ── AI Provider ──────────────────────────────────────────
    ai_provider: AIMode = AIMode.mock
    ai_mode: AIMode = AIMode.mock
    groq_api_key: str = ""
    groq_model: str = "openai/gpt-oss-120b"
    openai_api_key: str = ""
    openai_model: str = "gpt-4o"
    google_api_key: str = ""
    google_model: str = "gemini-1.5-pro"

    # ── Redis ────────────────────────────────────────────────
    redis_url: str = "redis://localhost:6379/0"

    # ── MCP ──────────────────────────────────────────────────
    mcp_mode: MCPMode = MCPMode.mock
    mcp_maps_url: str = "http://localhost:8010"
    mcp_civic_url: str = "http://localhost:8011"
    mcp_notification_url: str = "http://localhost:8012"
    mcp_policy_url: str = "http://localhost:8013"
    mcp_analytics_url: str = "http://localhost:8014"

    # ── Maps / GIS ───────────────────────────────────────────
    maps_api_key: str = ""
    geocoding_provider: str = "mock"

    # ── Email ────────────────────────────────────────────────
    email_host: str = "smtp.gmail.com"
    email_port: int = 587
    email_use_tls: bool = True
    email_user: str = ""
    email_password: str = ""
    email_from: str = "noreply@namma-civic.ai"

    # ── SMS ──────────────────────────────────────────────────
    sms_provider: str = "mock"
    twilio_account_sid: str = ""
    twilio_auth_token: str = ""
    twilio_from_number: str = ""

    # ── CORS ─────────────────────────────────────────────────
    cors_origins: str = "http://localhost:5173,http://localhost:3000"

    # ── File Storage ─────────────────────────────────────────
    upload_dir: str = "./uploads"
    max_upload_size_mb: int = 10

    # ── Rate Limiting ────────────────────────────────────────
    rate_limit_per_minute: int = 60
    sla_scan_interval_seconds: int = Field(default=300, ge=30)

    # ── Logging ──────────────────────────────────────────────
    log_level: str = "INFO"

    # ── Derived helpers ──────────────────────────────────────
    @property
    def cors_origins_list(self) -> List[str]:
        return [origin.strip() for origin in self.cors_origins.split(",")]

    @property
    def is_sqlite(self) -> bool:
        return self.database_mode == DatabaseMode.sqlite

    @property
    def is_postgresql(self) -> bool:
        return self.database_mode == DatabaseMode.postgresql

    @property
    def is_mock_ai(self) -> bool:
        return self.ai_mode == AIMode.mock

    @property
    def is_mock_mcp(self) -> bool:
        return self.mcp_mode == MCPMode.mock

    @property
    def max_upload_bytes(self) -> int:
        return self.max_upload_size_mb * 1024 * 1024


@lru_cache()
def get_settings() -> Settings:
    """Return cached application settings singleton."""
    return Settings()


# Convenience alias used throughout the codebase
settings = get_settings()


def get_upload_directory() -> str:
    """Return a writable upload location for the current runtime."""
    if (
        os.environ.get("VERCEL") == "1"
        or bool(os.environ.get("VERCEL_REGION"))
        or bool(os.environ.get("VERCEL_ENV"))
        or bool(os.environ.get("AWS_LAMBDA_FUNCTION_NAME"))
    ):
        return "/tmp/uploads"
    return settings.upload_dir
