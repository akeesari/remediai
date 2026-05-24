.PHONY: install dev stop api test test-unit test-agent-evals test-e2e lint format typecheck check-prompts ci migrate migrate-down ui ui-install ui-build ui-dev

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

ci: lint typecheck check-prompts test
