---
id: configuration
title: Configuration Reference
sidebar_label: Configuration Reference
---

# Configuration Reference

All RemediAI configuration is loaded via `pydantic-settings` from environment variables. No configuration is hard-coded. In production, secrets come from Azure Key Vault via the CSI driver; non-secret config comes from Kubernetes ConfigMaps or environment variables in the Helm chart.

---

## Full variable reference

### Azure identity

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `AZURE_TENANT_ID` | Yes | — | Azure AD tenant ID |
| `AZURE_CLIENT_ID` | Prod only | — | Managed Identity client ID (AKS) |
| `AZURE_CLIENT_SECRET` | Dev only | — | App registration secret (local dev only) |
| `AZURE_KEYVAULT_URL` | Yes | — | Key Vault endpoint URL |

---

### Application Insights / Azure Monitor

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `AZURE_MONITOR_APP_INSIGHTS_RESOURCE_ID` | No | — | Application Insights resource ID for Azure Monitor lookups |
| `AZURE_MONITOR_WORKSPACE_ID` | Yes | — | Log Analytics workspace resource ID |
| `INGESTION_POLL_INTERVAL_SECONDS` | No | `60` | Poll interval in seconds |
| `INGESTION_LOOKBACK_MINUTES` | No | `10` | Lookback window per poll cycle |

---

### Azure OpenAI

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `AZURE_OPENAI_ENDPOINT` | Yes | — | OpenAI resource endpoint |
| `AZURE_OPENAI_API_VERSION` | No | `2024-08-01-preview` | API version |
| `AZURE_OPENAI_DEPLOYMENT` | No | `gpt-4o` | Model deployment name |
| `AZURE_OPENAI_MAX_TOKENS` | No | `2048` | Max tokens per response |
| `AZURE_OPENAI_TEMPERATURE` | No | `0.1` | Sampling temperature |
| `AZURE_OPENAI_TIMEOUT` | No | `30` | Request timeout in seconds |
| `AZURE_OPENAI_MAX_RETRIES` | No | `3` | Retry attempts on 429 / 5xx |

---

### Azure AI Search

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `AZURE_SEARCH_ENDPOINT` | Yes | — | Search service endpoint |
| `AZURE_SEARCH_INDEX` | No | `remediai-rag` | Index name |
| `RAG_TOP_K` | No | `10` | Results requested from Search |
| `RAG_MIN_SCORE` | No | `0.6` | Minimum relevance score to include |
| `RAG_MAX_RESULTS` | No | `5` | Max results passed to Fix Planner |

---

### Azure DevOps

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `AZURE_DEVOPS_ORG_URL` | Yes | — | Organisation URL |
| `AZURE_DEVOPS_PROJECT` | Yes | — | Project name |
| `AZURE_DEVOPS_REPOSITORY` | No | — | Repository name for code context and PRs |
| `AZURE_DEVOPS_BRANCH` | No | `main` | Default branch |
| `AZURE_DEVOPS_PAT` | Yes | — | PAT (from Key Vault at runtime) |

---

### Database

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `POSTGRES_HOST` | No | `localhost` | PostgreSQL hostname |
| `POSTGRES_PORT` | No | `5432` | PostgreSQL port |
| `POSTGRES_DB` | No | `remediai` | Database name |
| `POSTGRES_USER` | No | `remediai` | Database user |
| `POSTGRES_PASSWORD` | Yes | — | Database password |

---

### Redis

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `REDIS_URL` | Yes | — | Redis connection URL |
| `LOCAL_MODE` | No | `false` | Enables local-only log bridge endpoints and poller |
| `LOCAL_LOG_BRIDGE_CONTAINERS` | No | `api,worker,dashboard` | Containers watched by the local log bridge |
| `LOCAL_INCIDENT_POLL_INTERVAL_SECONDS` | No | `10` | Local poll interval for new incidents |

---

### Code Context Agent

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `CODE_CONTEXT_MAX_SNIPPETS` | No | `5` | Max source snippets per incident |
| `CODE_CONTEXT_LINES_AROUND` | No | `20` | Context lines above/below target line |

---

### PR Agent

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `DASHBOARD_BASE_URL` | No | — | Dashboard URL for PR description links |

---

### FastAPI

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `API_HOST` | No | `0.0.0.0` | Bind address |
| `API_PORT` | No | `8000` | Listen port |
| `API_WORKERS` | No | `1` | Uvicorn worker count |
| `API_RELOAD` | No | `false` | Enable hot reload (dev only) |
| `LOG_LEVEL` | No | `info` | Log level (`debug`, `info`, `warning`, `error`) |
| `CORS_ORIGINS` | No | `http://localhost:5173` | Allowed CORS origins (comma-separated) |

---

## Configuration validation

All settings are validated at startup by `pydantic-settings`. If a required variable is missing, the process exits immediately with a descriptive error:

```
pydantic_settings.ValidationError: 2 validation errors for Settings
AZURE_OPENAI_ENDPOINT
  Field required [type=missing, ...]
AZURE_DEVOPS_PAT
  Field required [type=missing, ...]
```

---

## Loading order

1. `.env` file (local development only)
2. Environment variables
3. Azure Key Vault secrets (mounted as files via CSI driver in production)

Variables from Key Vault take precedence over environment variables in production.
