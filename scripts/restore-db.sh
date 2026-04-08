#!/usr/bin/env bash
# CULTR Ventures — Database Restore Script
# Restores PostgreSQL from the latest backup
set -euo pipefail

BACKUP_ROOT="/opt/backups"
COMPOSE_FILE="/opt/cultr-platform/docker/docker-compose.yml"

# Find latest backup
LATEST=$(ls -t "${BACKUP_ROOT}/daily/"*.tar.gz 2>/dev/null | head -1)

if [ -z "$LATEST" ]; then
  echo "✗ No backups found in ${BACKUP_ROOT}/daily/"
  exit 1
fi

echo "═══ Restoring from: ${LATEST} ═══"
echo ""
echo "⚠️  This will REPLACE the current database. Press Ctrl+C to cancel..."
sleep 5

# Extract backup
TEMP_DIR=$(mktemp -d)
tar xzf "${LATEST}" -C "${TEMP_DIR}"

# Restore PostgreSQL
echo "Restoring PostgreSQL..."
docker compose -f "${COMPOSE_FILE}" exec -T postgres \
  pg_restore -U cultr -d cultr_platform --clean --if-exists \
  < "${TEMP_DIR}/postgres.dump"

echo "✓ Database restored from ${LATEST}"

# Cleanup
rm -rf "${TEMP_DIR}"
