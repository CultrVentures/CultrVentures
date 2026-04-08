#!/usr/bin/env bash
# CULTR Ventures — Cloudflare Tunnel Health Check
set -euo pipefail

echo "═══ Cloudflare Tunnel Status ═══"
echo ""

# Check cloudflared service
if systemctl is-active --quiet cloudflared 2>/dev/null; then
  echo "✓ cloudflared service: RUNNING"
else
  echo "✗ cloudflared service: STOPPED"
  echo "  Run: sudo systemctl start cloudflared"
  exit 1
fi

# Check tunnel connectivity
echo ""
echo "── Tunnel Metrics ──"
curl -sf http://localhost:45678/metrics 2>/dev/null | grep -E "^cloudflared_tunnel" | head -20 || \
  echo "  (metrics endpoint not available)"

# Check routes
echo ""
echo "── Route Health ──"
for route in "cultrventures.com" "api.cultrventures.com" "knowledge.cultrventures.com"; do
  STATUS=$(curl -sf -o /dev/null -w "%{http_code}" "https://${route}/api/health" 2>/dev/null || echo "000")
  if [ "$STATUS" = "200" ]; then
    echo "  ✓ ${route} → ${STATUS}"
  else
    echo "  ✗ ${route} → ${STATUS}"
  fi
done

echo ""
echo "── Docker Services ──"
docker compose -f /opt/cultr-platform/docker/docker-compose.yml ps --format "table {{.Name}}\t{{.Status}}\t{{.Ports}}" 2>/dev/null || \
  echo "  (docker compose not available from this context)"
