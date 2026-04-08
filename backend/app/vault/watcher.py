"""
CULTR Ventures — Vault Watcher
Watches the Obsidian vault (memory/) for changes and triggers:
  1. Re-embedding of modified documents into Qdrant
  2. Grounding validation on agent-produced files
  3. CLAUDE.md hot cache invalidation
  4. Downstream agent notifications via Redis pub/sub

Runs as a standalone service (docker container: vault-watcher).
"""

import logging
import time
import json
from pathlib import Path

from watchfiles import watch, Change

logger = logging.getLogger("cultr.vault-watcher")

VAULT_PATH = Path("/app/memory")
WATCH_EXTENSIONS = {".md", ".yaml", ".yml"}

# Paths that trigger specific actions
GROUNDING_PATHS = {"outputs/", "clients/"}
EMBEDDING_PATHS = {"clients/", "context/", "projects/", "grounding/"}
HOT_CACHE_FILES = {"CLAUDE.md", "glossary.md"}


def start_watcher():
    """Main watcher loop — blocks forever, processing file changes."""
    logger.info(f"Starting vault watcher on {VAULT_PATH}")

    if not VAULT_PATH.exists():
        logger.error(f"Vault path does not exist: {VAULT_PATH}")
        return

    for changes in watch(VAULT_PATH, recursive=True):
        for change_type, path_str in changes:
            path = Path(path_str)

            # Only watch relevant extensions
            if path.suffix not in WATCH_EXTENSIONS:
                continue

            relative = path.relative_to(VAULT_PATH)
            logger.info(f"Vault change: {change_type.name} {relative}")

            try:
                _handle_change(change_type, path, relative)
            except Exception as e:
                logger.error(f"Error handling change {relative}: {e}", exc_info=True)


def _handle_change(change_type: Change, path: Path, relative: Path) -> None:
    """Route file changes to appropriate handlers."""
    rel_str = str(relative)

    # ── Re-embed modified documents ────────────────────────────────
    if change_type in (Change.added, Change.modified):
        if any(rel_str.startswith(p) for p in EMBEDDING_PATHS):
            _trigger_reembed(path)

    # ── Grounding validation on agent outputs ──────────────────────
    if change_type in (Change.added, Change.modified):
        if any(rel_str.startswith(p) for p in GROUNDING_PATHS):
            _trigger_grounding_check(path)

    # ── Hot cache invalidation ─────────────────────────────────────
    if path.name in HOT_CACHE_FILES:
        _invalidate_hot_cache(path)

    # ── Publish change event to Redis ──────────────────────────────
    _publish_change_event(change_type, relative)


def _trigger_reembed(path: Path) -> None:
    """Queue a re-embedding task for the changed document."""
    logger.info(f"Queueing re-embed for {path}")
    try:
        from app.workers.embedding_tasks import embed_document
        embed_document.delay(str(path))
    except Exception as e:
        logger.error(f"Failed to queue re-embed: {e}")


def _trigger_grounding_check(path: Path) -> None:
    """Run grounding validation on an agent-produced file."""
    logger.info(f"Queueing grounding validation for {path}")
    # Check if file has agent frontmatter
    try:
        content = path.read_text(encoding="utf-8")
        if content.startswith("---") and "agent:" in content[:500]:
            from app.workers.maintenance_tasks import validate_vault_grounding
            # Run inline validation (lightweight) instead of full sweep
            import subprocess
            result = subprocess.run(
                ["python", "/app/scripts/validate-grounding.py", str(path)],
                capture_output=True,
                text=True,
                timeout=30,
            )
            if result.returncode != 0:
                logger.warning(f"Grounding validation failed for {path}: {result.stdout}")
    except Exception as e:
        logger.error(f"Grounding check failed: {e}")


def _invalidate_hot_cache(path: Path) -> None:
    """Clear Redis cache entries that depend on hot cache files."""
    logger.info(f"Invalidating hot cache for {path.name}")
    try:
        import redis
        r = redis.from_url("redis://redis:6379/0")
        r.delete("cultr:hot_cache:CLAUDE.md")
        r.publish("cultr:cache_invalidation", json.dumps({
            "file": str(path.name),
            "action": "invalidate",
        }))
    except Exception as e:
        logger.error(f"Cache invalidation failed: {e}")


def _publish_change_event(change_type: Change, relative: Path) -> None:
    """Publish vault change event to Redis pub/sub."""
    try:
        import redis
        r = redis.from_url("redis://redis:6379/0")
        r.publish("cultr:vault_changes", json.dumps({
            "type": change_type.name,
            "path": str(relative),
            "timestamp": time.time(),
        }))
    except Exception:
        pass  # Non-critical — don't fail on pub/sub errors


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
    start_watcher()
