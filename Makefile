# ═══════════════════════════════════════════════════════════════════
# CULTR Ventures — Monorepo Makefile
# Unified command interface for development, deployment, and ops
# ═══════════════════════════════════════════════════════════════════

.DEFAULT_GOAL := help
SHELL := /bin/bash

# ── Variables ─────────────────────────────────────────────────────
COMPOSE := docker compose -f docker/docker-compose.yml
COMPOSE_GPU := docker compose -f docker/docker-compose.gpu.yml
BACKEND := backend
FRONTEND := frontend/astro
PYTHON := python3

# ── Help ──────────────────────────────────────────────────────────
.PHONY: help
help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-24s\033[0m %s\n", $$1, $$2}'

# ═══════════════════════════════════════════════════════════════════
#  DEVELOPMENT
# ═══════════════════════════════════════════════════════════════════

.PHONY: dev dev-backend dev-frontend dev-up dev-down dev-logs

dev: dev-up ## Start full development stack
	@echo "✓ Dev stack running — API: http://localhost:8000  Frontend: http://localhost:4321"

dev-backend: ## Start backend only (FastAPI with hot reload)
	cd $(BACKEND) && uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

dev-frontend: ## Start frontend only (Astro dev server)
	cd $(FRONTEND) && npm run dev

dev-up: ## Start all Docker services
	$(COMPOSE) up -d

dev-down: ## Stop all Docker services
	$(COMPOSE) down

dev-logs: ## Tail logs from all services
	$(COMPOSE) logs -f --tail=100

# ═══════════════════════════════════════════════════════════════════
#  BUILD
# ═══════════════════════════════════════════════════════════════════

.PHONY: build build-backend build-frontend build-acp

build: build-backend build-acp build-frontend ## Build everything

build-backend: ## Build backend Docker image
	docker build -f docker/Dockerfile.backend -t cultr-backend:latest .

build-acp: ## Build ACP runtime Docker image
	docker build -f docker/Dockerfile.acp -t cultr-acp:latest .

build-frontend: ## Build Astro site
	cd $(FRONTEND) && npm ci && npm run build

# ═══════════════════════════════════════════════════════════════════
#  TESTING & LINTING
# ═══════════════════════════════════════════════════════════════════

.PHONY: test test-backend lint lint-backend lint-frontend typecheck validate-grounding

test: test-backend ## Run all tests

test-backend: ## Run backend tests
	cd $(BACKEND) && $(PYTHON) -m pytest tests/ -v --tb=short

lint: lint-backend lint-frontend ## Run all linters

lint-backend: ## Lint Python code (ruff)
	ruff check $(BACKEND)/

lint-frontend: ## Lint frontend (Astro check)
	cd $(FRONTEND) && npx astro check

typecheck: ## Type check backend (mypy)
	mypy $(BACKEND)/app/ --ignore-missing-imports

validate-grounding: ## Validate grounding rules on vault files
	$(PYTHON) scripts/validate-grounding.py --all

ci: lint typecheck test validate-grounding ## Run full CI pipeline locally

# ═══════════════════════════════════════════════════════════════════
#  DEPLOYMENT
# ═══════════════════════════════════════════════════════════════════

.PHONY: deploy deploy-backend deploy-frontend deploy-workers

deploy: deploy-backend deploy-frontend ## Deploy everything

deploy-backend: ## Deploy backend to Hetzner AX52
	./scripts/deploy.sh backend

deploy-frontend: ## Deploy frontend to Cloudflare Pages
	cd $(FRONTEND) && npm run build
	npx wrangler pages deploy $(FRONTEND)/dist --project-name=cultr-site

deploy-workers: ## Deploy Cloudflare Workers
	cd .cloudflare/workers/auth-middleware && npx wrangler deploy
	cd .cloudflare/workers/rate-limiter && npx wrangler deploy

# ═══════════════════════════════════════════════════════════════════
#  DATABASE
# ═══════════════════════════════════════════════════════════════════

.PHONY: db-shell db-migrate db-reset db-backup db-restore

db-shell: ## Open PostgreSQL shell
	$(COMPOSE) exec postgres psql -U cultr -d cultr_platform

db-migrate: ## Run database migrations
	cd $(BACKEND) && alembic upgrade head

db-reset: ## Reset database (DESTRUCTIVE)
	@echo "⚠️  This will destroy all data. Press Ctrl+C to cancel..."
	@sleep 3
	$(COMPOSE) exec postgres psql -U cultr -d cultr_platform -f /docker-entrypoint-initdb.d/init-db.sql

db-backup: ## Create database backup
	./scripts/backup.sh

db-restore: ## Restore from latest backup
	@echo "Restoring from latest backup..."
	./scripts/restore-db.sh

# ═══════════════════════════════════════════════════════════════════
#  GPU NODE
# ═══════════════════════════════════════════════════════════════════

.PHONY: gpu-up gpu-down gpu-logs gpu-status

gpu-up: ## Start GPU services on GEX44
	ssh cultr@10.0.0.2 "cd /opt/cultr-gpu && docker compose up -d"

gpu-down: ## Stop GPU services
	ssh cultr@10.0.0.2 "cd /opt/cultr-gpu && docker compose down"

gpu-logs: ## Tail GPU service logs
	ssh cultr@10.0.0.2 "cd /opt/cultr-gpu && docker compose logs -f --tail=50"

gpu-status: ## Check GPU utilization
	ssh cultr@10.0.0.2 "nvidia-smi"

# ═══════════════════════════════════════════════════════════════════
#  INFRASTRUCTURE
# ═══════════════════════════════════════════════════════════════════

.PHONY: infra-plan infra-apply tunnel-status monitoring

infra-plan: ## Terraform plan
	cd infra/terraform && terraform plan

infra-apply: ## Terraform apply
	cd infra/terraform && terraform apply

tunnel-status: ## Check Cloudflare Tunnel health
	./scripts/tunnel-status.sh

monitoring: ## Open Grafana dashboard
	@echo "Grafana: http://localhost:3000 (admin/admin)"
	@echo "Prometheus: http://localhost:9090"

# ═══════════════════════════════════════════════════════════════════
#  UTILITIES
# ═══════════════════════════════════════════════════════════════════

.PHONY: clean cost-report setup

setup: ## Initial project setup
	cp .env.example .env
	cd $(FRONTEND) && npm install
	pip install -r $(BACKEND)/requirements.txt
	@echo "✓ Setup complete. Edit .env with your secrets, then run: make dev"

clean: ## Remove build artifacts and caches
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name .pytest_cache -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name node_modules -exec rm -rf {} + 2>/dev/null || true
	rm -rf $(FRONTEND)/dist $(FRONTEND)/.astro
	@echo "✓ Cleaned"

cost-report: ## Generate monthly infrastructure cost report
	./scripts/cost-report.sh
