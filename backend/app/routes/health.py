"""
Health check endpoints — used by Docker HEALTHCHECK, monitoring, and Cloudflare Tunnel.
"""

from datetime import datetime, timezone

from fastapi import APIRouter

router = APIRouter()


@router.get("/api/health")
async def health_check():
    """Basic liveness probe."""
    return {
        "status": "healthy",
        "service": "cultr-platform",
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


@router.get("/api/health/ready")
async def readiness_check():
    """
    Readiness probe — checks all dependencies.
    TODO: Add actual dependency checks (DB, Redis, Qdrant).
    """
    checks = {
        "database": "ok",  # TODO: actual pg check
        "redis": "ok",  # TODO: actual redis ping
        "qdrant": "ok",  # TODO: actual qdrant health
    }
    all_ok = all(v == "ok" for v in checks.values())
    return {
        "status": "ready" if all_ok else "degraded",
        "checks": checks,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
