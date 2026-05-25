.PHONY: install dev stop api test test-unit test-agent-evals test-e2e lint format typecheck security-scan check-prompts ci ci-local install-hooks migrate migrate-down ui ui-install ui-build ui-dev index-populate local-up local-down local-logs local-migrate local-smoke

PYTHON ?= python3

install:
	pip install poetry && poetry install

dev:
	docker compose -f docker-compose.dev.yml up -d

stop:
	docker compose -f docker-compose.dev.yml down

api:
	uvicorn apps.api.main:app --reload --host 0.0.0.0 --port 8000

test:
	pytest tests/ -x -v --ignore=tests/e2e

test-unit:
	pytest tests/unit/ -v

test-agent-evals:
	pytest tests/agent-evals/ -v

test-e2e:
	pytest tests/e2e/ -v -m e2e

lint:
	ruff check .

format:
	ruff format .

typecheck:
	mypy apps/ packages/ --strict

check-prompts:
	$(PYTHON) scripts/validate_prompt_contracts.py

security-scan:
	python -m pip install --quiet pip-audit detect-secrets
	pip-audit
	cd apps/dashboard && npm install --legacy-peer-deps && npm audit --audit-level=moderate
	detect-secrets-hook --baseline .secrets.baseline $$(git ls-files)

migrate:
	alembic upgrade head

migrate-down:
	alembic downgrade -1

ui-install:
	cd apps/dashboard && npm install --legacy-peer-deps

ui-build:
	cd apps/dashboard && npm run build

ui-dev:
	cd apps/dashboard && npm run dev

index-populate:
	$(PYTHON) scripts/populate_search_index.py --source all

local-up:
	cp -n .env.local.example .env.local || true
	docker compose -f docker-compose.local.yml --env-file .env.local up --build -d

local-down:
	docker compose -f docker-compose.local.yml down

local-logs:
	docker compose -f docker-compose.local.yml logs -f

local-migrate:
	docker compose -f docker-compose.local.yml exec api alembic upgrade head

local-bridge-e2e:
	@echo "Running local log bridge end-to-end tests against http://localhost:$${LOCAL_API_PORT:-8000}"
	@echo "Prereqs: make local-up && make local-migrate"
	pytest tests/e2e/test_local_log_bridge.py -v -m local_bridge \
		--tb=short \
		-x

local-bridge-restart:
	docker compose -f docker-compose.local.yml --env-file .env.local restart log-bridge

local-bridge-logs:
	docker compose -f docker-compose.local.yml logs -f log-bridge

local-smoke:
	@set -a; [ -f .env.local ] && . ./.env.local; set +a; \
	api_port=$${LOCAL_API_PORT:-8000}; \
	dashboard_port=$${LOCAL_DASHBOARD_PORT:-3000}; \
	echo "Checking API health on $$api_port"; \
	curl -sSf "http://localhost:$$api_port/health" >/dev/null; \
	echo "Checking API docs on $$api_port"; \
	curl -sSf -I "http://localhost:$$api_port/docs" | grep -q "200"; \
	echo "Checking dashboard on $$dashboard_port"; \
	curl -sSf -I "http://localhost:$$dashboard_port" | grep -q "200"; \
	echo "Local smoke checks passed"

ci: lint typecheck check-prompts test

install-hooks:
	poetry run pre-commit install --hook-type pre-commit --hook-type pre-push

ci-local: lint typecheck security-scan check-prompts test ui-build
