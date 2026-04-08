"""
CULTR Ventures — Agent Task Workers
Implements the Stateless Agent Protocol (5-step lifecycle):
  1. Hydrate  — Read state from vault
  2. Validate — Check inputs against Pydantic schema
  3. Execute  — Run the agent's skill
  4. Persist  — Write results to vault with grounding metadata
  5. Signal   — Notify downstream agents / update task status

Each task is fully stateless — no conversation history dependency.
"""

import logging
import json
from datetime import datetime, timezone
from pathlib import Path

from celery import shared_task
from pydantic import BaseModel, ValidationError

logger = logging.getLogger("cultr.agents")


class AgentTaskInput(BaseModel):
    """Validated input for any agent task."""
    agent_id: str
    task_type: str
    client_id: str | None = None
    context: dict = {}
    priority: str = "normal"


class AgentTaskResult(BaseModel):
    """Required output schema with grounding metadata."""
    agent_id: str
    task_type: str
    output: dict
    source_ref: str
    confidence: float
    grounding_status: str  # verified | derived | assumption
    review_status: str = "pending"
    unknowns: list[str] = []
    assumptions: list[str] = []


@shared_task(
    bind=True,
    name="app.workers.agent_tasks.execute_agent_task",
    max_retries=2,
    default_retry_delay=30,
    acks_late=True,
)
def execute_agent_task(self, task_data: dict) -> dict:
    """
    Main entry point for all agent tasks.
    Follows the Stateless Agent Protocol lifecycle.
    """
    task_id = self.request.id
    logger.info(f"[{task_id}] Starting agent task: {task_data.get('agent_id')}")

    # ── Step 1: Hydrate — Read state from vault ────────────────────
    try:
        input_data = AgentTaskInput(**task_data)
    except ValidationError as e:
        logger.error(f"[{task_id}] Validation failed: {e}")
        return {"status": "failed", "error": f"Input validation failed: {e}"}

    vault_state = _hydrate_from_vault(input_data.agent_id, input_data.client_id)
    logger.info(f"[{task_id}] Hydrated vault state: {len(vault_state)} files read")

    # ── Step 2: Validate — Check prerequisites ─────────────────────
    validation_errors = _validate_prerequisites(input_data, vault_state)
    if validation_errors:
        logger.warning(f"[{task_id}] Prerequisites not met: {validation_errors}")
        return {"status": "blocked", "errors": validation_errors}

    # ── Step 3: Execute — Run the agent skill ──────────────────────
    try:
        result = _execute_skill(input_data, vault_state)
    except Exception as e:
        logger.error(f"[{task_id}] Execution failed: {e}", exc_info=True)
        # Retry on transient failures
        if self.request.retries < self.max_retries:
            raise self.retry(exc=e)
        return {"status": "failed", "error": str(e)}

    # ── Step 4: Persist — Write to vault with grounding ────────────
    try:
        vault_path = _persist_to_vault(input_data, result)
        logger.info(f"[{task_id}] Persisted to vault: {vault_path}")
    except Exception as e:
        logger.error(f"[{task_id}] Persistence failed: {e}")
        return {"status": "failed", "error": f"Vault write failed: {e}"}

    # ── Step 5: Signal — Notify downstream ─────────────────────────
    _signal_completion(input_data, result, vault_path)

    return {
        "status": "completed",
        "agent_id": input_data.agent_id,
        "vault_path": str(vault_path),
        "confidence": result.confidence,
        "grounding_status": result.grounding_status,
        "review_status": result.review_status,
    }


def _hydrate_from_vault(agent_id: str, client_id: str | None) -> dict:
    """
    Read relevant vault state for this agent + client.
    Returns dict of filename -> content.
    """
    vault_path = Path("/app/memory")
    state = {}

    # Agent-specific config
    agent_config = vault_path / "agents" / f"{agent_id}.md"
    if agent_config.exists():
        state["agent_config"] = agent_config.read_text()

    # Client context if applicable
    if client_id:
        client_dir = vault_path / "clients" / client_id
        if client_dir.exists():
            for f in client_dir.glob("*.md"):
                state[f"client/{f.name}"] = f.read_text()

    # System rules (always loaded)
    grounding_rules = vault_path / "system" / "grounding-rules.md"
    if grounding_rules.exists():
        state["grounding_rules"] = grounding_rules.read_text()

    return state


def _validate_prerequisites(input_data: AgentTaskInput, vault_state: dict) -> list[str]:
    """Check that all prerequisites for this task are met."""
    errors = []

    # Must have grounding rules loaded
    if "grounding_rules" not in vault_state:
        errors.append("Missing grounding rules in vault — cannot execute safely")

    # Client tasks need client context
    if input_data.client_id and not any(k.startswith("client/") for k in vault_state):
        errors.append(f"No vault state found for client {input_data.client_id}")

    return errors


def _execute_skill(input_data: AgentTaskInput, vault_state: dict) -> AgentTaskResult:
    """
    Execute the agent's skill.
    TODO: Route to actual Claude Agent SDK / skill handlers.
    """
    # Placeholder — real implementation dispatches to Claude Agent SDK
    return AgentTaskResult(
        agent_id=input_data.agent_id,
        task_type=input_data.task_type,
        output={"message": "Task execution placeholder — implement skill routing"},
        source_ref="internal/placeholder",
        confidence=0.0,
        grounding_status="assumption",
        review_status="pending",
        unknowns=["Actual skill execution not yet implemented"],
        assumptions=[],
    )


def _persist_to_vault(input_data: AgentTaskInput, result: AgentTaskResult) -> Path:
    """Write task result to vault with required grounding frontmatter."""
    vault_path = Path("/app/memory")
    timestamp = datetime.now(timezone.utc).isoformat()

    # Build output path
    output_dir = vault_path / "outputs" / input_data.agent_id
    output_dir.mkdir(parents=True, exist_ok=True)
    output_file = output_dir / f"{input_data.task_type}_{timestamp[:10]}.md"

    # Build frontmatter
    frontmatter = {
        "agent": result.agent_id,
        "skill": result.task_type,
        "timestamp": timestamp,
        "source_type": "computation",
        "source_ref": result.source_ref,
        "confidence": result.confidence,
        "grounding_status": result.grounding_status,
        "review_status": result.review_status,
    }

    # Write with YAML frontmatter
    import yaml
    content = "---\n"
    content += yaml.dump(frontmatter, default_flow_style=False)
    content += "---\n\n"
    content += f"# {result.task_type} — {result.agent_id}\n\n"
    content += json.dumps(result.output, indent=2)

    if result.unknowns:
        content += "\n\n## Unknowns\n"
        for u in result.unknowns:
            content += f"- Unknown: {u}\n"

    if result.assumptions:
        content += "\n\n## ⚠️ Assumptions\n"
        for a in result.assumptions:
            content += f"> ⚠️ {a}\n"

    output_file.write_text(content)
    return output_file


def _signal_completion(
    input_data: AgentTaskInput,
    result: AgentTaskResult,
    vault_path: Path,
) -> None:
    """Notify downstream systems of task completion."""
    logger.info(
        f"Agent {input_data.agent_id} completed {input_data.task_type} "
        f"→ confidence={result.confidence}, grounding={result.grounding_status}"
    )
    # TODO: Push to Redis pub/sub for real-time UI updates
    # TODO: Trigger downstream agent tasks if needed
    # TODO: Update agent_tasks table status
