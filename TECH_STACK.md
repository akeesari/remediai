# RemediAI — Technology Stack

## Summary

| Layer               | Technology                              | Rationale                                                      |
| ------------------- | --------------------------------------- | -------------------------------------------------------------- |
| Backend API         | Python 3.12 + FastAPI                   | Async-native, Pydantic-first, strong Azure SDK support         |
| Agent Worker        | Python 3.12                             | Consistent with API; rich AI/ML ecosystem                      |
| Agent Orchestration | LangGraph                               | Stateful, graph-based agent workflows; native LangChain compat |
| AI Platform         | Azure AI Foundry / Azure OpenAI GPT-4.1 (default) + portable adapters | Azure-optimized by default while preserving cloud-agnostic deployment profiles |
| RAG                 | Azure AI Search (hybrid)                | Integrated vector + keyword search; Azure-native               |
| Log Source          | Application Insights / Azure Monitor KQL (MVP) · Grafana Loki (Phase 27) · Webhook / OpenTelemetry (Phase 38+) | MVP targets Azure Monitor; architecture supports pluggable ingestion sources |
| Work Queue          | PostgreSQL `incidents.status` column    | No broker required; ACID guarantees prevent double-processing  |
| Database            | PostgreSQL 16 on AKS                    | Reliable relational store kept on the cluster network          |
| Cache               | Redis 7 on AKS                          | API response caching and deduplication without an external cache tier |
| Target Registry     | PostgreSQL `monitor_targets`            | Persisted allowlist for local container and Kubernetes target selection |
| Storage             | Azure Blob Storage                      | Evidence bundles, prompt files, large agent artifacts          |
| Source Control      | Azure DevOps Repos (MVP) · GitHub (Phase 38) | Abstracted via `SourceControlAdapter`; provider selected per repository |
| Work Items          | Azure DevOps Boards (MVP) · Jira (Phase 29) | Abstracted via `TicketProvider`; provider selected per project |
| UI Framework        | React 18 + TypeScript                   | Component ecosystem; type safety                               |
| UI Build            | Vite                                    | Fast dev server; ESM-native                                    |
| UI State            | React Query (TanStack Query)            | Server state management; cache + refetch                       |
| Containerization    | Docker                                  | Consistent build and deploy artifacts                          |
| Orchestration       | AKS (Azure Kubernetes Service)          | Production hosting; Workload Identity; KEDA scaling            |
| Autoscaling         | KEDA                                    | Event-driven scaling off PostgreSQL incident queue depth       |
| Secrets             | Azure Key Vault                         | Central secret management; CSI driver mount to pods            |
| Identity            | Managed Identity / Workload Identity    | No secret rotation; Azure-native zero-trust                    |
| Migrations          | Alembic                                 | Versioned PostgreSQL schema migrations                         |
| Testing             | pytest + pytest-asyncio                 | Async test support; fixture-based                              |
| Linting             | Ruff                                    | Fast Python linter + formatter                                 |
| Type Checking       | mypy (strict)                           | End-to-end type safety                                         |
| CI/CD               | Azure DevOps Pipelines (YAML)           | Native ADO integration; build, test, deploy                    |
| Observability       | OpenTelemetry + Azure Monitor           | Distributed tracing; structured logging                        |
| Metrics             | Prometheus + Azure Managed Grafana      | Pod-level and application metrics                              |
| Infrastructure      | Terraform                               | Declarative Azure resource provisioning                        |
| Helm                | Helm 3                                  | Kubernetes deployment packaging                                |

---

## Python Dependencies (Key)

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
azure-search-documents = "^11.6"
azure-storage-blob = "^12.20"
azure-keyvault-secrets = "^4.8"

# Database
sqlalchemy = "^2.0"
alembic = "^1.13"
asyncpg = "^0.29"
greenlet = "^3.1"

# Cache
redis = {extras = ["asyncio"], version = "^5.0"}

# Observability
opentelemetry-sdk = "^1.25"
opentelemetry-instrumentation-fastapi = "^0.46"
structlog = "^24.2"
```

---

## Frontend Dependencies (Key)

```json
{
  "dependencies": {
    "react": "^18.3",
    "react-dom": "^18.3",
    "react-router-dom": "^6.24",
    "@tanstack/react-query": "^5.48",
    "axios": "^1.7",
    "recharts": "^2.12",
    "@radix-ui/react-dialog": "^1.1",
    "tailwindcss": "^3.4",
    "clsx": "^2.1"
  },
  "devDependencies": {
    "typescript": "^5.4",
    "vite": "^5.3",
    "vitest": "^1.6",
    "@testing-library/react": "^16.0",
    "eslint": "^9.6",
    "@typescript-eslint/eslint-plugin": "^7.16"
  }
}
```

---

## Local Development

Local development uses Docker Compose to run the same dependency shape used in AKS:

```yaml
services:
  postgres:
    image: postgres:16
    environment:
      POSTGRES_DB: remediai
      POSTGRES_USER: remediai
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD:-change_me_locally}

  redis:
    image: redis:7-alpine
```

Azure services (OpenAI, AI Search, DevOps, Monitor) are accessed via real Azure credentials in dev. Use a dedicated non-production Azure subscription.

---

## Version Pinning Policy

- Pin major and minor versions for all production dependencies.
- Pin major only for dev/test tooling.
- Run `pip-audit` and `npm audit` in CI to catch known vulnerabilities.
- Dependabot enabled for automated patch-level updates with PR review.
