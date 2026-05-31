---
sidebar_position: 2
title: Installation
---

# Installation

This guide sets up RemediAI for local development against real Azure services.

---

## 1. Clone the repository

```bash
git clone https://github.com/akeesari/remediai.git
cd remediai
```

---

## 2. Configure environment variables

Copy the example environment file and fill in your Azure resource values:

```bash
cp .env.example .env
```

Open `.env` and fill in:

```bash
# Azure credentials
AZURE_TENANT_ID=<your-tenant-id>
AZURE_CLIENT_ID=<managed-identity-or-app-registration-client-id>
AZURE_CLIENT_SECRET=<client-secret-if-using-app-registration>

# Application Insights / Azure Monitor
AZURE_MONITOR_WORKSPACE_ID=<workspace-resource-id>
AZURE_MONITOR_APP_INSIGHTS_RESOURCE_ID=/subscriptions/<sub>/resourceGroups/<rg>/providers/microsoft.insights/components/<app-insights>

# Azure OpenAI
AZURE_OPENAI_ENDPOINT=https://<resource>.openai.azure.com/
AZURE_OPENAI_API_VERSION=2024-02-15-preview
AZURE_OPENAI_DEPLOYMENT=gpt-4o

# Azure AI Search
AZURE_SEARCH_ENDPOINT=https://<resource>.search.windows.net
AZURE_SEARCH_INDEX=remediai-rag

# Azure DevOps
AZURE_DEVOPS_ORG_URL=https://dev.azure.com/<org>
AZURE_DEVOPS_PROJECT=<project>
AZURE_DEVOPS_REPOSITORY=<repo>
AZURE_DEVOPS_PAT=<your-pat-from-key-vault>

# Azure Key Vault
AZURE_KEYVAULT_URL=https://<vault>.vault.azure.net

# PostgreSQL
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_DB=remediai
POSTGRES_USER=remediai
POSTGRES_PASSWORD=change_me_locally

# Redis
REDIS_URL=redis://localhost:6379

# Polling interval (seconds)
INGESTION_POLL_INTERVAL_SECONDS=60
```

:::danger Never commit `.env`
The `.env` file is in `.gitignore`. Never commit it. Real credentials must come from Azure Key Vault in any non-local environment.
:::

---

## 3. Install Python dependencies

```bash
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install poetry
poetry install
```

---

## 4. Start local dependencies

PostgreSQL and Redis run in Docker for local development:

```bash
make local-up
```

This runs `docker compose --env-file .env up -d`. To view logs:

```bash
make local-logs
```

---

## 5. Run database migrations

```bash
make local-migrate
```

This runs Alembic migrations against the local PostgreSQL container:

```bash
alembic upgrade head
```

---

## 6. Start the API

```bash
cd apps/api
uvicorn main:app --reload --port 8000
```

The API is now available at `http://localhost:8000`. Check the health endpoint:

```bash
curl http://localhost:8000/health
# {"status":"ok","version":"0.4.0"}
```

---

## 7. Install and start the dashboard

```bash
cd apps/dashboard
npm install
npm run dev
```

The React dashboard is available at `http://localhost:5173`.

---

## 8. Start the agent worker

In a new terminal:

```bash
cd apps/worker
python -m worker.main
```

The worker connects to the Service Bus subscription and starts listening for `IncidentEvent` messages.

---

## Verify the installation

Run the smoke test to confirm all services are connected:

```bash
make local-smoke
```

Expected output:

```
✓ API health check
✓ PostgreSQL connection
✓ Redis connection
✓ Service Bus connection
✓ Azure OpenAI reachable
✓ Azure AI Search reachable
✓ Azure DevOps reachable
All checks passed.
```

---

## Stopping the stack

```bash
make local-down
```

---

## Next step

With the stack running, proceed to [Your First Incident](./first-incident) to trigger and trace a complete pipeline run.
