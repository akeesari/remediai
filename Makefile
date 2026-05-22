.PHONY: install dev stop api test test-unit lint format typecheck ci migrate migrate-down

install:
	pip install poetry && poetry install

dev:
	docker compose -f docker-compose.dev.yml up -d

stop:
	docker compose -f docker-compose.dev.yml down

api:
	uvicorn apps.api.main:app --reload --host 0.0.0.0 --port 8000

test:
	pytest tests/ -x -v

test-unit:
	pytest tests/unit/ -v

lint:
	ruff check .

format:
	ruff format .

typecheck:
	mypy apps/ packages/ --strict

migrate:
	alembic upgrade head

migrate-down:
	alembic downgrade -1

ci: lint typecheck test
