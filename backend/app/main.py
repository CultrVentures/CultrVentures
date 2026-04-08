"""
CULTR Ventures — FastAPI Application Entry Point
Serves: REST API + MCP Server + Agent Workers + Vault Watcher
"""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.routes import health, auth, agents, clients, mcp_server, acp
from app.middleware.grounding import GroundingMiddleware
from app.middleware.request_id import RequestIdMiddleware

settings = get_settings()

# ── Logging ─────────────────────────────────────────────────────────
logging.basicConfig(
    level=getattr(logging, settings.LOG_LEVEL),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("cultr")


# ── Lifespan ────────────────────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup/shutdown lifecycle."""
    logger.info(f"Starting {settings.APP_NAME} v{settings.APP_VERSION}")
    logger.info(f"Environment: {settings.ENVIRONMENT}")

    # TODO: Initialize database pool
    # TODO: Initialize Qdrant client
    # TODO: Initialize Redis connection
    # TODO: Start vault watcher

    yield

    # TODO: Cleanup connections
    logger.info("Shutting down")


# ── App ─────────────────────────────────────────────────────────────
app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    docs_url="/api/docs" if settings.DEBUG else None,
    redoc_url="/api/redoc" if settings.DEBUG else None,
    lifespan=lifespan,
)

# ── Middleware (order matters — outermost first) ────────────────────
app.add_middleware(RequestIdMiddleware)
app.add_middleware(GroundingMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Routes ──────────────────────────────────────────────────────────
app.include_router(health.router, tags=["Health"])
app.include_router(auth.router, prefix=settings.API_PREFIX, tags=["Auth"])
app.include_router(agents.router, prefix=settings.API_PREFIX, tags=["Agents"])
app.include_router(clients.router, prefix=settings.API_PREFIX, tags=["Clients"])
app.include_router(mcp_server.router, prefix=settings.API_PREFIX, tags=["MCP"])
app.include_router(acp.router, prefix=settings.API_PREFIX, tags=["ACP"])
