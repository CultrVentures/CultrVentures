#!/usr/bin/env bash
# CULTR Ventures — Monthly Infrastructure Cost Report
set -euo pipefail

echo "═══════════════════════════════════════════════════════════"
echo "  CULTR VENTURES — Infrastructure Cost Report"
echo "  Generated: $(date '+%Y-%m-%d %H:%M UTC')"
echo "═══════════════════════════════════════════════════════════"
echo ""

# ── Fixed Infrastructure Costs ─────────────────────────────────────
echo "── Fixed Monthly Costs ──"
printf "  %-36s %8s\n" "Hetzner AX52 (compute)" "€64.00"
printf "  %-36s %8s\n" "Hetzner GEX44 (GPU)" "€184.00"
printf "  %-36s %8s\n" "Cloudflare Pro" "€0.00"
printf "  %-36s %8s\n" "Domain (cultrventures.com)" "~€1.00"
echo "  ──────────────────────────────────────────────"
printf "  %-36s %8s\n" "TOTAL FIXED" "~€249.00"
echo ""

# ── API Costs (estimate from usage) ───────────────────────────────
echo "── Variable Costs (API Usage) ──"
echo "  Checking token usage from vault..."

# Count vault writes this month as a proxy for agent activity
MONTH=$(date +%Y-%m)
VAULT_WRITES=$(find /opt/cultr-platform/memory -name "*.md" -newer /tmp/month-start 2>/dev/null | wc -l || echo "N/A")

echo "  Vault writes this month: ${VAULT_WRITES}"
echo ""
echo "  ⚠️  For accurate API costs, check:"
echo "     → Anthropic Console: https://console.anthropic.com/usage"
echo "     → OpenAI Dashboard:  https://platform.openai.com/usage"
echo "     → Stripe Dashboard:  https://dashboard.stripe.com"
echo ""

# ── Resource Utilization ──────────────────────────────────────────
echo "── Current Resource Utilization ──"
echo "  AX52 (Compute):"
printf "    CPU:    %s\n" "$(uptime | awk -F'load average:' '{print $2}' | xargs)"
printf "    Memory: %s\n" "$(free -h | awk '/Mem:/ {printf "%s / %s (%.0f%%)", $3, $2, $3/$2*100}')"
printf "    Disk:   %s\n" "$(df -h / | awk 'NR==2 {printf "%s / %s (%s)", $3, $2, $5}')"
echo ""

# Check GPU node if reachable
if ssh -q -o ConnectTimeout=3 cultr@10.0.0.2 "echo ok" >/dev/null 2>&1; then
  echo "  GEX44 (GPU):"
  ssh cultr@10.0.0.2 "nvidia-smi --query-gpu=utilization.gpu,memory.used,memory.total --format=csv,noheader" 2>/dev/null | \
    awk -F', ' '{printf "    GPU:    %s utilization, VRAM: %s / %s\n", $1, $2, $3}'
else
  echo "  GEX44 (GPU): Not reachable"
fi

echo ""
echo "═══════════════════════════════════════════════════════════"
echo "  Target: <€300/mo infra + <\$150/client/mo API"
echo "═══════════════════════════════════════════════════════════"
