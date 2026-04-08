#!/usr/bin/env bash
# ═══════════════════════════════════════════════════════════════════
# CULTR Ventures — Deploy Script
# Deploys backend to Hetzner AX52 via SSH (no open ports — tunnel only)
# ═══════════════════════════════════════════════════════════════════
set -euo pipefail

COMPONENT="${1:-all}"
REMOTE_USER="cultr"
REMOTE_HOST="${HETZNER_AX52_IP:?Set HETZNER_AX52_IP}"
REMOTE_DIR="/opt/cultr-platform"
COMPOSE_FILE="docker/docker-compose.yml"

log() { echo "[$(date '+%H:%M:%S')] $*"; }
err() { log "ERROR: $*" >&2; exit 1; }

# ── Pre-flight checks ──────────────────────────────────────────────
check_ssh() {
  ssh -q -o ConnectTimeout=5 "${REMOTE_USER}@${REMOTE_HOST}" "echo ok" >/dev/null 2>&1 \
    || err "Cannot reach ${REMOTE_HOST}. Check SSH key and network."
}

# ── Deploy backend ──────────────────────────────────────────────────
deploy_backend() {
  log "Deploying backend to ${REMOTE_HOST}..."

  ssh "${REMOTE_USER}@${REMOTE_HOST}" bash -s <<'REMOTE_SCRIPT'
    set -euo pipefail
    cd /opt/cultr-platform

    # Pull latest
    git fetch origin main
    LOCAL=$(git rev-parse HEAD)
    REMOTE=$(git rev-parse origin/main)

    if [ "$LOCAL" = "$REMOTE" ]; then
      echo "Already up to date at $(git rev-parse --short HEAD)"
      exit 0
    fi

    echo "Updating from $(git rev-parse --short HEAD) to $(git rev-parse --short origin/main)..."
    git pull origin main

    # Build and deploy with zero downtime
    docker compose -f docker/docker-compose.yml build --no-cache fastapi celery-worker
    docker compose -f docker/docker-compose.yml up -d --remove-orphans

    # Health check (retry up to 30s)
    echo "Running health check..."
    for i in $(seq 1 6); do
      if docker compose -f docker/docker-compose.yml exec -T fastapi \
          curl -sf http://localhost:8000/api/health >/dev/null 2>&1; then
        echo "✓ Health check passed"
        exit 0
      fi
      echo "  Waiting for health check... (attempt $i/6)"
      sleep 5
    done

    echo "✗ Health check failed — rolling back"
    git checkout "$LOCAL"
    docker compose -f docker/docker-compose.yml up -d --remove-orphans
    exit 1
REMOTE_SCRIPT

  log "✓ Backend deployed successfully"
}

# ── Deploy GPU services ─────────────────────────────────────────────
deploy_gpu() {
  log "Deploying GPU services to GEX44 (via AX52 jump)..."

  ssh -J "${REMOTE_USER}@${REMOTE_HOST}" "${REMOTE_USER}@10.0.0.2" bash -s <<'REMOTE_SCRIPT'
    set -euo pipefail
    cd /opt/cultr-gpu
    docker compose pull
    docker compose up -d --remove-orphans
    echo "✓ GPU services updated"
REMOTE_SCRIPT

  log "✓ GPU services deployed"
}

# ── Main ────────────────────────────────────────────────────────────
main() {
  log "Starting deployment: ${COMPONENT}"
  check_ssh

  case "${COMPONENT}" in
    backend)  deploy_backend ;;
    gpu)      deploy_gpu ;;
    all)      deploy_backend; deploy_gpu ;;
    *)        err "Unknown component: ${COMPONENT}. Use: backend | gpu | all" ;;
  esac

  log "Deploy complete at $(date)"
}

main
