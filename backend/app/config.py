"""
CULTR Ventures — Application Configuration
Single source of truth for all environment-driven settings.
"""

from functools import lru_cache
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """App settings loaded from environment variables / .env file."""

    # ── App ─────────────────────────────────────────────────────────
    APP_NAME: str = "CULTR Ventures Platform"
    APP_VERSION: str = "0.1.0"
    DEBUG: bool = False
    LOG_LEVEL: str = "INFO"
    ENVIRONMENT: str = "production"  # production | staging | development

    # ── API ─────────────────────────────────────────────────────────
    API_PREFIX: str = "/api/v1"
    ALLOWED_ORIGINS: list[str] = [
        "https://cultrventures.com",
        "https://www.cultrventures.com",
        "https://portal.cultrventures.com",
    ]

    # ── Database (PostgreSQL + pgvector) ────────────────────────────
    DATABASE_URL: str = "postgresql://cultr:changeme@localhost:5432/cultr_platform"
    DB_POOL_SIZE: int = 20
    DB_MAX_OVERFLOW: int = 10

    # ── Redis ───────────────────────────────────────────────────────
    REDIS_URL: str = "redis://localhost:6379/0"
    REDIS_CACHE_TTL: int = 3600  # 1 hour default

    # ── Vector Store (Qdrant) ───────────────────────────────────────
    QDRANT_URL: str = "http://localhost:6333"
    QDRANT_COLLECTION: str = "cultr_knowledge"
    EMBEDDING_DIM: int = 1024  # BGE-large-en-v1.5

    # ── Auth (Supabase-compatible JWT) ──────────────────────────────
    JWT_SECRET: str = "changeme"
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRY_MINUTES: int = 60
    JWT_REFRESH_EXPIRY_DAYS: int = 30

    # ── Anthropic (Claude) ──────────────────────────────────────────
    ANTHROPIC_API_KEY: str = ""
    CLAUDE_PRIMARY_MODEL: str = "claude-opus-4-6"
    CLAUDE_EXECUTION_MODEL: str = "claude-sonnet-4-6"
    CLAUDE_MONITORING_MODEL: str = "claude-haiku-4-5-20251001"

    # ── Local LLM (vLLM on GPU node) ───────────────────────────────
    VLLM_URL: str = "http://10.0.0.2:8080"
    VLLM_MODEL: str = "google/gemma-2-9b-it-AWQ"

    # ── Local Embeddings (GPU node) ─────────────────────────────────
    EMBEDDINGS_URL: str = "http://10.0.0.2:8081"
    EMBEDDINGS_MODEL: str = "BAAI/bge-large-en-v1.5"

    # ── Stripe ──────────────────────────────────────────────────────
    STRIPE_SECRET_KEY: str = ""
    STRIPE_WEBHOOK_SECRET: str = ""
    STRIPE_PRICE_STARTER: str = ""
    STRIPE_PRICE_GROWTH: str = ""
    STRIPE_PRICE_ENTERPRISE: str = ""

    # ── Virtuals ACP ────────────────────────────────────────────────
    ACP_WALLET_KEY: str = ""
    ACP_RUNTIME_URL: str = "http://localhost:18790"

    # ── Vault (Obsidian) ────────────────────────────────────────────
    VAULT_PATH: str = "/app/memory"

    # ── Celery ──────────────────────────────────────────────────────
    CELERY_BROKER_URL: str = "redis://localhost:6379/1"
    CELERY_RESULT_BACKEND: str = "redis://localhost:6379/2"

    # ── Monitoring ──────────────────────────────────────────────────
    PROMETHEUS_ENABLED: bool = True

    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "case_sensitive": True,
    }


@lru_cache()
def get_settings() -> Settings:
    """Cached settings singleton."""
    return Settings()
