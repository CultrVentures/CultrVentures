"""
CULTR Ventures — Celery Application
Central Celery instance used by all agent workers.
"""

from celery import Celery
from celery.schedules import crontab

from app.config import get_settings

settings = get_settings()

celery_app = Celery(
    "cultr",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND,
)

celery_app.conf.update(
    # Serialization
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",

    # Timeouts & limits
    task_time_limit=600,          # Hard kill after 10 min
    task_soft_time_limit=540,     # Soft warning at 9 min
    task_acks_late=True,          # Ack after execution (crash safety)
    worker_prefetch_multiplier=1, # One task at a time per worker

    # Result expiry
    result_expires=3600,          # 1 hour

    # Task routing — agents go to agent queue, heavy tasks to gpu queue
    task_routes={
        "app.workers.agent_tasks.*": {"queue": "agents"},
        "app.workers.embedding_tasks.*": {"queue": "gpu"},
        "app.workers.maintenance_tasks.*": {"queue": "maintenance"},
    },

    # Periodic tasks (Celery Beat)
    beat_schedule={
        "grounding-validation-sweep": {
            "task": "app.workers.maintenance_tasks.validate_vault_grounding",
            "schedule": crontab(minute=0, hour="*/6"),  # Every 6 hours
        },
        "cost-tracking-snapshot": {
            "task": "app.workers.maintenance_tasks.snapshot_cost_metrics",
            "schedule": crontab(minute=0, hour=0),  # Daily midnight
        },
        "tool-reliability-update": {
            "task": "app.workers.maintenance_tasks.update_tool_reliability",
            "schedule": crontab(minute=30, hour="*/12"),  # Every 12 hours
        },
        "stale-task-cleanup": {
            "task": "app.workers.maintenance_tasks.cleanup_stale_tasks",
            "schedule": crontab(minute=0, hour=2),  # 2 AM daily
        },
    },
)

# Auto-discover tasks from worker modules
celery_app.autodiscover_tasks([
    "app.workers.agent_tasks",
    "app.workers.embedding_tasks",
    "app.workers.maintenance_tasks",
])
