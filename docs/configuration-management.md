# Configuration Management

All application configuration is loaded via `pydantic-settings` from `apps/api/core/config.py`.
Variables are read from environment or `.env` at startup.
Production secrets are managed in Azure Key Vault and injected at runtime via Managed Identity.

**Local setup:** `cp .env.example .env` — never commit `.env`.

---

## Docker Compose — Host Port Overrides

Only needed when the default port is already in use on your machine. These variables are Compose-only and are never read by the application.

| Variable | Description | Secret | Default |
|---|---|---|---|
| `PG_HOST_PORT` | Host-side port mapped to the Postgres container | No | `5432` |
| `REDIS_HOST_PORT` | Host-side port mapped to the Redis container | No | `6379` |
| `API_HOST_PORT` | Host-side port mapped to the API container | No | `8000` |
| `DASHBOARD_HOST_PORT` | Host-side port mapped to the dashboard container | No | `3000` |
| `DOCS_HOST_PORT` | Host-side port mapped to the docs container | No | `3001` |

---

## Database

| Variable | Description | Secret | Default |
|---|---|---|---|
| `DATABASE_URL` | Full async PostgreSQL connection string | No | `postgresql+asyncpg://remediai:change_me_locally@localhost:5432/remediai` |
| `POSTGRES_PASSWORD` | Password for the Postgres container — used by docker-compose to initialise the database, not by the app | **Yes** | `***` |

> `DATABASE_URL` is the single source of truth for the application. `POSTGRES_PASSWORD` is a postgres-official env var consumed only by the postgres container at init time; the password must also appear inside `DATABASE_URL`.

---

## Redis

| Variable | Description | Secret | Default |
|---|---|---|---|
| `REDIS_URL` | Redis connection URL | No | `redis://localhost:6379/0` |

---

## Azure Identity

Read directly by the Azure SDK — not declared in `Settings`. Leave blank when using Managed Identity or `az login`.

| Variable | Description | Secret | Default |
|---|---|---|---|
| `AZURE_TENANT_ID` | AAD tenant ID for service-principal authentication | No | — |
| `AZURE_CLIENT_ID` | Service principal client (application) ID | No | — |
| `AZURE_CLIENT_SECRET` | Service principal client secret | **Yes** | `***` |

---

## Azure Monitor

| Variable | Description | Secret | Default |
|---|---|---|---|
| `AZURE_MONITOR_WORKSPACE_ID` | Log Analytics workspace resource ID | No | — |

---

## Provider Profile

Selects the integration backend for each capability. See `docs/specs/phase-32-provider-abstraction-profiles.md`.

| Variable | Description | Secret | Default |
|---|---|---|---|
| `REMEDIAI_PROFILE` | Predefined provider bundle (`azure-foundry`, `openai-portable`) | No | `azure-foundry` |
| `LLM_PROVIDER_ID` | LLM provider (`azure-openai`, `portable`) | No | `azure-openai` |
| `RETRIEVAL_PROVIDER_ID` | Retrieval provider (`azure-ai-search`, `portable`) | No | `azure-ai-search` |
| `SCM_PROVIDER_ID` | Source control provider (`auto`, `github`, `azure-devops`) | No | `auto` |
| `TICKET_PROVIDER_ID` | Ticketing provider (`none`, `azure-devops`, `jira`) | No | `none` |

---

## Azure OpenAI

| Variable | Description | Secret | Default |
|---|---|---|---|
| `AZURE_OPENAI_ENDPOINT` | Azure OpenAI resource endpoint URL | No | — |
| `AZURE_OPENAI_DEPLOYMENT` | Deployed model name | No | `gpt-4.1` |
| `AZURE_OPENAI_API_VERSION` | REST API version string | No | `2024-08-01-preview` |

---

## Portable OpenAI-Compatible Provider

Used when `LLM_PROVIDER_ID=portable`. Credentials must be stored in secret management for production.

| Variable | Description | Secret | Default |
|---|---|---|---|
| `PORTABLE_OPENAI_BASE_URL` | Base URL for the OpenAI-compatible endpoint | No | — |
| `PORTABLE_OPENAI_API_KEY` | API key for the portable LLM provider | **Yes** | `***` |
| `PORTABLE_OPENAI_MODEL` | Model name to request | No | `gpt-4.1-mini` |

---

## Azure AI Search

| Variable | Description | Secret | Default |
|---|---|---|---|
| `AZURE_SEARCH_ENDPOINT` | Azure AI Search service endpoint URL | No | — |
| `AZURE_SEARCH_INDEX` | Index name for the RAG document store | No | `remediai-rag` |
| `AZURE_SEARCH_API_KEY` | Azure AI Search admin/query key | **Yes** | `***` |
| `AZURE_SEARCH_INCIDENTS_INDEX` | Index name used by the search index population script | No | `remediai-incidents` |
| `OPENAI_EMBEDDING_MODEL` | Embedding model name for RAG ingestion | No | `text-embedding-3-small` |
| `OPENAI_EMBEDDING_DEPLOYMENT` | Azure OpenAI embedding deployment name (blank for portable) | No | — |
| `ADO_SOURCE_PATH_PREFIX` | Path prefix within the ADO repo to index | No | `src/` |

---

## Azure DevOps

| Variable | Description | Secret | Default |
|---|---|---|---|
| `AZURE_DEVOPS_ORG_URL` | Azure DevOps organization URL | No | — |
| `AZURE_DEVOPS_PROJECT` | Project name within the organization | No | — |
| `AZURE_DEVOPS_REPOSITORY` | Repository name for code context and bug creation | No | — |
| `AZURE_DEVOPS_BRANCH` | Default branch name | No | `main` |
| `AZURE_DEVOPS_PAT` | Personal Access Token for ADO API calls | **Yes** | `***` |

---

## Application

| Variable | Description | Secret | Default |
|---|---|---|---|
| `APP_ENV` | Runtime environment tag (`development`, `staging`, `production`) | No | `development` |
| `LOG_LEVEL` | Structlog minimum log level | No | `INFO` |

> `X-Correlation-ID` is the fixed correlation header name. It is a code constant, not an env var.

---

## Ingestion

| Variable | Description | Secret | Default |
|---|---|---|---|
| `INGESTION_POLL_INTERVAL_SECONDS` | How often the ingestion worker polls Azure Monitor (seconds) | No | `60` |
| `INGESTION_LOOKBACK_MINUTES` | How far back to look for new incidents on each poll | No | `10` |

---

## Local Dev Mode

`LOCAL_MODE` is not set in `.env.example`. Docker Compose defaults it to `true`; the `Settings` class defaults it to `false` for production.

| Variable | Description | Secret | Default |
|---|---|---|---|
| `BRIDGE_CONTAINERS` | Comma-separated Docker Compose service names monitored by the log-bridge and used by the API target discovery | No | `api,worker,dashboard` |
| `TARGET_API_TOKEN` | Bearer token required by `/api/v1/targets*` in non-local mode | **Yes** | `***` |
| `KUBERNETES_DISCOVERY_NAMESPACES` | Comma-separated Kubernetes namespaces to auto-discover workload targets | No | — |
| `KUBERNETES_DISCOVERY_WORKLOADS` | Comma-separated `namespace/workload` entries to expose as targets | No | — |

---

## Log Bridge (direct env vars — not via `Settings`)

Read by `apps/log_bridge/main.py` via `os.environ.get`, not through pydantic-settings. Set by docker-compose directly.

| Variable | Description | Secret | Default |
|---|---|---|---|
| `API_URL` | Internal URL the log-bridge uses to push events to the API | No | `http://api:8000` |
| `COMPOSE_PROJECT_NAME` | Docker Compose project name | No | `remediai` |
| `BRIDGE_CONTAINERS` | Same variable as above — consumed by both the log-bridge service and the API settings | No | `api,worker,dashboard` |

---

## Migrations (alembic + test infrastructure)

| Variable | Description | Secret | Default |
|---|---|---|---|
| `DATABASE_URL` | Full async connection string read by alembic and docker-compose | No | falls back to alembic.ini default |
| `TEST_DATABASE_URL` | Database URL used by integration/E2E tests | No | computed from `DATABASE_URL` default |

---

## Removed Variables

| Variable | Reason |
|---|---|
| `POSTGRES_HOST`, `POSTGRES_PORT`, `POSTGRES_DB`, `POSTGRES_USER` | Consolidated into `DATABASE_URL`; individual fields removed from `Settings` |
| `AZURE_MONITOR_APP_INSIGHTS_RESOURCE_ID` | Defined in config but never read by any code |
| `ADO_SOURCE_REPO` | Defined in config but never read by any code |
| `CORRELATION_ID_HEADER` | Promoted to a code constant (`X-Correlation-ID`); not operator-configurable |
| `SEARCH_INDEX_NAME` | Renamed to `AZURE_SEARCH_INCIDENTS_INDEX` for naming consistency |
| `LOCAL_LOG_BRIDGE_CONTAINERS` | Renamed to `BRIDGE_CONTAINERS` so both the log-bridge app and API settings share one env var name |
| `LOCAL_POSTGRES_PORT`, `LOCAL_REDIS_PORT`, `LOCAL_API_PORT`, `LOCAL_DASHBOARD_PORT`, `LOCAL_DOCS_PORT` | Renamed to `PG_HOST_PORT`, `REDIS_HOST_PORT`, `API_HOST_PORT`, `DASHBOARD_HOST_PORT`, `DOCS_HOST_PORT` to remove the misleading `LOCAL_` prefix |
| `AZURE_KEYVAULT_URL` | Azure SDK resolves Key Vault via Managed Identity; no code reads this variable |
