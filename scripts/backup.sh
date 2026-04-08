#!/usr/bin/env bash
# ═══════════════════════════════════════════════════════════════════
# CULTR Ventures — Backup Script
# Daily backup: PostgreSQL + Qdrant snapshots + vault + config
# Keeps 7 daily, 4 weekly, 3 monthly backups
# ═══════════════════════════════════════════════════════════════════
set -euo pipefail

BACKUP_ROOT="/opt/backups"
DATE=$(date +%Y-%m-%d_%H%M)
BACKUP_DIR="${BACKUP_ROOT}/daily/${DATE}"
COMPOSE_FILE="/opt/cultr-platform/docker/docker-compose.yml"

log() { echo "[$(date '+%H:%M:%S')] $*"; }

mkdir -p "${BACKUP_DIR}"

# ── PostgreSQL ──────────────────────────────────────────────────────
log "Backing up PostgreSQL..."
docker compose -f "${COMPOSE_FILE}" exec -T postgres \
  pg_dump -U cultr -d cultr_platform --format=custom \
  > "${BACKUP_DIR}/postgres.dump"
log "  ✓ PostgreSQL: $(du -sh "${BACKUP_DIR}/postgres.dump" | cut -f1)"

# ── Qdrant snapshots ───────────────────────────────────────────────
log "Backing up Qdrant collections..."
QDRANT_URL="http://localhost:6333"
for collection in $(curl -sf "${QDRANT_URL}/collections" | jq -r '.result.collections[].name' 2>/dev/null); do
  curl -sf -X POST "${QDRANT_URL}/collections/${collection}/snapshots" \
    -o "${BACKUP_DIR}/qdrant_${collection}.snapshot" || true
  log "  ✓ Qdrant collection: ${collection}"
done

# ── Vault (Obsidian) ───────────────────────────────────────────────
log "Backing up vault..."
tar czf "${BACKUP_DIR}/vault.tar.gz" \
  -C /opt/cultr-platform memory/ CLAUDE.md \
  --exclude='*.obsidian' 2>/dev/null || true
log "  ✓ Vault: $(du -sh "${BACKUP_DIR}/vault.tar.gz" | cut -f1)"

# ── Config files ───────────────────────────────────────────────────
log "Backing up config..."
tar czf "${BACKUP_DIR}/config.tar.gz" \
  -C /opt/cultr-platform \
  .env docker/docker-compose.yml \
  infra/terraform/terraform.tfstate 2>/dev/null || true

# ── Compress full backup ───────────────────────────────────────────
log "Compressing..."
ARCHIVE="${BACKUP_ROOT}/daily/cultr-backup-${DATE}.tar.gz"
tar czf "${ARCHIVE}" -C "${BACKUP_DIR}" .
rm -rf "${BACKUP_DIR}"
log "✓ Backup complete: ${ARCHIVE} ($(du -sh "${ARCHIVE}" | cut -f1))"

# ── Retention policy ───────────────────────────────────────────────
log "Applying retention policy..."

# Keep 7 daily backups
ls -t "${BACKUP_ROOT}/daily/"*.tar.gz 2>/dev/null | tail -n +8 | xargs rm -f 2>/dev/null || true

# Weekly: copy Sunday's backup
if [ "$(date +%u)" = "7" ]; then
  mkdir -p "${BACKUP_ROOT}/weekly"
  cp "${ARCHIVE}" "${BACKUP_ROOT}/weekly/"
  ls -t "${BACKUP_ROOT}/weekly/"*.tar.gz 2>/dev/null | tail -n +5 | xargs rm -f 2>/dev/null || true
fi

# Monthly: copy 1st of month
if [ "$(date +%d)" = "01" ]; then
  mkdir -p "${BACKUP_ROOT}/monthly"
  cp "${ARCHIVE}" "${BACKUP_ROOT}/monthly/"
  ls -t "${BACKUP_ROOT}/monthly/"*.tar.gz 2>/dev/null | tail -n +4 | xargs rm -f 2>/dev/null || true
fi

log "✓ Retention applied (7 daily, 4 weekly, 3 monthly)"
