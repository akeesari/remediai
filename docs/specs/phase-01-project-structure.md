# Phase 1 — Project Structure & Application Scaffold

## Objective

Create the complete repository skeleton for RemediAI: all directory structure,
Python project configuration (`pyproject.toml`), Docker Compose dev environment,
FastAPI application shell with a working `/health` endpoint, structured logging,
`pydantic-settings` configuration, and pytest infrastructure.

After this phase:
- `pytest tests/unit/` passes
- `ruff check .` passes with zero violations
- `mypy apps/api/ --strict` passes with zero errors
- `uvicorn apps.api.main:app` starts and `GET /health` returns `{"status": "ok"}`
- All directories from `README.md` exist on disk

## Milestone

`ROADMAP.md` — Milestone 1: Foundation  
Check off: `Repository structure scaffolded` and `Basic FastAPI app with health check endpoint`

---

## Files to Create

### Root config
```
pyproject.toml
docker-compose.yml
Makefile
.python-version
```

### API — `apps/api/`
```
apps/api/__init__.py
apps/api/main.py
apps/api/core/__init__.py
apps/api/core/config.py
apps/api/core/logging.py
apps/api/routers/__init__.py
```

### Worker stubs — `apps/worker/`
```
apps/worker/__init__.py
apps/worker/ingestion/__init__.py
apps/worker/agents/__init__.py
```

### Dashboard stub — `apps/dashboard/`
```
apps/dashboard/.gitkeep
```

### Shared packages — `packages/`
```
packages/__init__.py
packages/domain/__init__.py
packages/integrations/__init__.py
packages/agent_runtime/__init__.py
packages/data_access/__init__.py
```

### Tests
```
tests/__init__.py
tests/conftest.py
tests/unit/__init__.py
tests/unit/test_health.py
tests/integration/__init__.py
tests/e2e/__init__.py
tests/agent-evals/__init__.py
```

### Docs & infrastructure stubs
```
docs/prompts/.gitkeep
docs/runbooks/.gitkeep
docs/product/.gitkeep
docs/architecture/.gitkeep
infrastructure/terraform/.gitkeep
infrastructure/helm/.gitkeep
infrastructure/k8s/.gitkeep
pipelines/azure-devops/.gitkeep
```

---

## Files to Modify

| File | Change |
| --- | --- |
| `ROADMAP.md` | Check off `Repository structure scaffolded` and `Basic FastAPI app with health check endpoint` under Milestone 1 |
| `README.md` | Update "Repository Structure" tree if any directory names differ from what was created |

---

## Dependencies

All from `TECH_STACK.md`. Define them all in `pyproject.toml` now even if not used until later phases — so future phases just `poetry install` and run without touching `pyproject.toml` again.

```toml
[tool.poetry.dependencies]
python = "^3.12"

# API
fastapi = "^0.115"
uvicorn = {extras = ["standard"], version = "^0.30"}
pydantic = "^2.7"
pydantic-settings = "^2.3"

# Agent
langgraph = "^0.2"
langchain-openai = "^0.2"
langchain-community = "^0.3"

# Azure
azure-identity = "^1.17"
azure-monitor-query = "^1.3"
azure-servicebus = "^7.12"
azure-search-documents = "^11.6"
azure-storage-blob = "^12.20"
azure-keyvault-secrets = "^4.8"

# Database
sqlalchemy = "^2.0"
alembic = "^1.13"
asyncpg = "^0.29"

# Cache
redis = {extras = ["asyncio"], version = "^5.0"}

# Observability
opentelemetry-sdk = "^1.25"
opentelemetry-instrumentation-fastapi = "^0.46"
structlog = "^24.2"

[tool.poetry.group.dev.dependencies]
pytest = "^8.2"
pytest-asyncio = "^0.23"
httpx = "^0.27"
ruff = "^0.4"
mypy = "^1.10"
```

---

## Implementation Notes

### `pyproject.toml` — tool configuration sections

```toml
[tool.pytest.ini_options]
asyncio_mode = "auto"
testpaths = ["tests"]

[tool.mypy]
strict = true
python_version = "3.12"
ignore_missing_imports = true

[tool.ruff]
target-version = "py312"
line-length = 100

[tool.ruff.lint]
select = ["E", "F", "I", "UP", "B", "SIM"]
ignore = ["E501"]
```

### `apps/api/core/config.py`

Use `pydantic-settings` `BaseSettings`. Every field maps 1-to-1 to a variable in `.env.example`.
Provide safe defaults for all non-secret fields. `postgres_password` defaults to `"change_me_locally"` in dev.
Add a `database_url` computed `@property` that returns the full `postgresql+asyncpg://` URL.
Wrap in `@lru_cache` `get_settings()` factory for dependency injection.

```python
from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_env: str = "development"
    log_level: str = "INFO"
    correlation_id_header: str = "X-Correlation-ID"

    postgres_host: str = "localhost"
    postgres_port: int = 5432
    postgres_db: str = "remediai"
    postgres_user: str = "remediai"
    postgres_password: str = "change_me_locally"

    redis_url: str = "redis://localhost:6379/0"

    azure_openai_endpoint: str = ""
    azure_openai_deployment: str = "gpt-4o"
    azure_openai_api_version: str = "2024-08-01-preview"

    azure_servicebus_namespace: str = ""
    azure_servicebus_topic: str = "incident-events"
    azure_servicebus_subscription: str = "agent-worker"

    azure_devops_org_url: str = ""
    azure_devops_project: str = ""
    azure_devops_pat: str = ""

    azure_search_endpoint: str = ""
    azure_search_index: str = "remediai-rag"

    azure_monitor_workspace_id: str = ""

    ingestion_poll_interval_seconds: int = 60
    ingestion_lookback_minutes: int = 10

    @property
    def database_url(self) -> str:
        return (
            f"postgresql+asyncpg://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )

@lru_cache
def get_settings() -> Settings:
    return Settings()
```

### `apps/api/core/logging.py`

Configure `structlog` with:
- JSON renderer when `app_env != "development"`, `ConsoleRenderer` otherwise
- Processors: `add_log_level`, `add_logger_name`, `TimeStamper(fmt="iso")`, `ExceptionRenderer`, `StackInfoRenderer`
- Bind `service="remediai-api"` globally via `structlog.contextvars`
- Export `get_logger` function used by all modules

### `apps/api/main.py`

```python
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from apps.api.core.config import get_settings
from apps.api.core.logging import get_logger, configure_logging

settings = get_settings()
configure_logging(settings.app_env, settings.log_level)
logger = get_logger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("remediai_api_starting", env=settings.app_env)
    yield
    logger.info("remediai_api_stopped")

app = FastAPI(
    title="RemediAI API",
    version="0.1.0",
    description="AI-powered exception analysis and remediation platform",
    lifespan=lifespan,
)

@app.middleware("http")
async def correlation_id_middleware(request: Request, call_next):
    # Extract or generate correlation ID, bind to structlog context
    ...

@app.get("/health", tags=["system"])
async def health() -> dict:
    return {"status": "ok", "version": "0.1.0", "env": settings.app_env}
```

### `tests/conftest.py`

```python
import pytest
from httpx import AsyncClient, ASGITransport
from apps.api.main import app

@pytest.fixture
async def client() -> AsyncClient:
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        yield ac
```

### `tests/unit/test_health.py`

Two tests:
1. `GET /health` returns HTTP 200
2. Response JSON contains `{"status": "ok"}`

### `docker-compose.yml`

```yaml
services:
  postgres:
    image: postgres:16
    environment:
      POSTGRES_DB: remediai
      POSTGRES_USER: remediai
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD:-change_me_locally}
    ports:
      - "5432:5432"
    volumes:
      - postgres_data:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U remediai"]
      interval: 5s
      timeout: 5s
      retries: 5

  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 5s
      timeout: 3s
      retries: 5

volumes:
  postgres_data:
```

### `Makefile`

```makefile
.PHONY: install dev test lint typecheck format ci

install:
	pip install poetry && poetry install

dev:
  docker compose up -d

stop:
  docker compose down

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

ci: lint typecheck test
```

### `.python-version`

```
3.12
```

---

## Acceptance Criteria

Run all commands from the repo root. Every command must exit with code 0.

- [ ] `poetry install` completes with no errors
- [ ] `docker compose config` validates successfully
- [ ] `python -c "from apps.api.main import app; print('OK')"` prints `OK`
- [ ] `python -c "from apps.api.core.config import get_settings; print(get_settings().app_env)"` prints `development`
- [ ] `pytest tests/unit/test_health.py -v` — both tests pass
- [ ] `ruff check .` — exits 0, no violations
- [ ] `mypy apps/api/ --strict` — exits 0, no errors
- [ ] `docker compose up -d && sleep 3 && docker compose ps` — postgres and redis show as healthy
- [ ] All directories below exist:
  ```
  apps/api/  apps/worker/  apps/dashboard/
  packages/domain/  packages/integrations/
  packages/agent_runtime/  packages/data_access/
  infrastructure/terraform/  infrastructure/helm/  infrastructure/k8s/
  pipelines/azure-devops/
  tests/unit/  tests/integration/  tests/e2e/  tests/agent-evals/
  docs/specs/  docs/prompts/  docs/runbooks/
  ```

---

## Commit Message

```
feat(scaffold): initialise project structure and FastAPI application shell

- pyproject.toml with all Python dependencies pinned (Poetry)
- docker-compose.yml: PostgreSQL 16 + Redis 7 with healthchecks
- FastAPI app: /health endpoint, correlation ID middleware, structlog JSON logging
- pydantic-settings Settings with all env vars mapped from .env.example
- pytest infrastructure: AsyncClient fixture, asyncio_mode=auto
- ruff + mypy strict configuration
- Full directory scaffold matching README.md structure
- Makefile: install, dev, test, lint, typecheck, format, ci targets
```
