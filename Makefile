# Cross-platform task runner for Unilead
# Usage: make <target>

.PHONY: help install dev test lint format build clean docker-up docker-down

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-20s\033[0m %s\n", $$1, $$2}'

install: ## Install all dependencies
	cd apps/api && pip install -r requirements.txt
	cd apps/web && npm install

dev: ## Start both backend + frontend in dev mode
	cd apps/api && python -m app.main &
	cd apps/web && npm run dev

test: test-backend test-frontend ## Run all tests

test-backend: ## Run backend tests
	cd apps/api && python -m pytest tests/ -v --tb=short

test-frontend: ## Run frontend tests
	cd apps/web && npx vitest run

lint: lint-backend lint-frontend ## Run all linters

lint-backend: ## Lint backend with ruff
	cd apps/api && ruff check app/ tests/

lint-frontend: ## Lint frontend
	cd apps/web && npm run lint

format: ## Format all code
	cd apps/api && ruff format app/ tests/
	cd apps/web && npx prettier --write "src/**/*.{ts,tsx}"

build: ## Build frontend for production
	cd apps/web && npm run build

clean: ## Remove build artifacts
	cd apps/web && rm -rf dist node_modules
	cd apps/api && rm -rf __pycache__ .pytest_cache
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true

docker-up: ## Start with Docker Compose
	docker-compose up --build -d

docker-down: ## Stop Docker Compose
	docker-compose down
