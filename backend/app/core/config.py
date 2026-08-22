"""
Application configuration.

All values are read from the environment, with safe development defaults.
Never hardcode secrets here — use the environment-variable chain and the
companion ``.env(.example)`` files.
"""
from __future__ import annotations

import os
from functools import lru_cache
from typing import List, Optional

from pydantic_settings import BaseSettings

# ---------------------------------------------------------------- settings --
class Settings(BaseSettings):
    """Central typed configuration for the Imad backend."""

    # Core
    APP_NAME: str = "Imad"
    APP_ENV: str = "development"  # development | staging | production
    DEBUG: bool = True
    API_V1_PREFIX: str = "/api/v1"
    BACKEND_CORS_ORIGINS: str = "http://localhost:5173,http://localhost:3000"

    # Security
    SECRET_KEY: str = "dev-insecure-secret-change-me"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 1440
    REFRESH_TOKEN_EXPIRE_MINUTES: int = 43200

    # Database
    DATABASE_URL: str = "sqlite:///./imad.db"

    # AI (reserved for Sprint 3+)
    AI_PROVIDER: str = "openai"
    OPENAI_API_KEY: Optional[str] = None
    ANTHROPIC_API_KEY: Optional[str] = None
    AI_MODEL: str = "gpt-4o-mini"
    AI_MAX_TOKENS: int = 2048
    AI_TEMPERATURE: float = 0.2

    # Structural engine
    STRUCTURAL_ENGINE_MAX_CRITICAL_SECTIONS: int = 64

    # Upload constraints
    MAX_UPLOAD_SIZE_MB: int = 128
    ALLOWED_CAD_EXTENSIONS: str = ".dxf,.dwg,.ifc,.obj"
    ALLOWED_NONCAD_EXTENSIONS: str = ".pdf,.png,.jpg,.jpeg,.tiff,.webp"
    SURVEY_MAX_ENTRIES: int = 5000

    class Config:
        """Pydantic v1-style env_prefix is omitted; keys map 1:1 to env vars."""
        env_file = ".env"
        case_sensitive = False

    # -- helpers ------------------------------------------------------
    @property
    def cors_origin_list(self) -> List[str]:
        """Parsed, cleaned list of allowed CORS origins."""
        return [o.strip() for o in self.BACKEND_CORS_ORIGINS.split(",") if o.strip()]

    @property
    def allowed_cad_extensions(self) -> List[str]:
        return [e.strip().lower() for e in self.ALLOWED_CAD_EXTENSIONS.split(",")]

    @property
    def allowed_noncad_extensions(self) -> List[str]:
        return [e.strip().lower() for e in self.ALLOWED_NONCAD_EXTENSIONS.split(",")]


@lru_cache
def get_settings() -> Settings:
    """Return the (cached) application settings singleton."""
    return Settings()