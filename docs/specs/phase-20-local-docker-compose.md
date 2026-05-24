# Phase 20 — Local Full-Stack Docker Compose

## Goal

Create Dockerfiles for all three application services and a full-stack
`docker-compose.local.yml` that runs the entire RemediAI platform locally —
API, Agent Worker, Dashboard, Postgres, Redis, and a Service Bus emulator —
so any developer can spin up the complete stack and verify it from a browser
without any Azure credentials.

This phase is the prerequisite for Phase 21 (CI pipeline) which builds the
same images, and replaces the partial `docker-compose.dev.yml` (which only
runs Postgres and Redis) for full-stack local testing.

---

## Deliverables

| Artifact | Description |
|---|---|
| `apps/api/Dockerfile` | Multi-stage Python image for the FastAPI backend |
| `apps/worker/Dockerfile` | Multi-stage Python image for the agent worker |
| `apps/dashboard/Dockerfile` | Node build stage + Nginx serve stage for the React SPA |
| `apps/dashboard/nginx.conf` | Nginx config: serve static files, proxy `/api` to the API container |
| `docker-compose.local.yml` | Full-stack compose: all 3 apps + Postgres + Redis + Service Bus emulator |
| `.env.local.example` | Example env file for local stack (no real Azure credentials required) |
| `Makefile` update | `local-up`, `local-down`, `local-logs` targets |

---

## Dockerfiles

### `apps/api/Dockerfile`

```dockerfile
FROM python:3.12-slim AS base
WORKDIR /app

RUN pip install poetry==1.8.3

COPY pyproject.toml poetry.lock ./
RUN poetry install --no-root --only main

COPY . .

FROM base AS production
EXPOSE 8000
CMD ["uvicorn", "apps.api.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

### `apps/worker/Dockerfile`

```dockerfile
FROM python:3.12-slim AS base
WORKDIR /app

RUN pip install poetry==1.8.3

COPY pyproject.toml poetry.lock ./
RUN poetry install --no-root --only main

COPY . .

FROM base AS production
CMD ["python", "-m", "apps.worker.main"]
```

### `apps/dashboard/Dockerfile`

```dockerfile
FROM node:20-alpine AS build
WORKDIR /app
COPY apps/dashboard/package*.json ./
RUN npm install --legacy-peer-deps
COPY apps/dashboard/ .
ARG VITE_API_BASE_URL=/api
ENV VITE_API_BASE_URL=${VITE_API_BASE_URL}
RUN npm run build

FROM nginx:1.27-alpine AS production
COPY --from=build /app/dist /usr/share/nginx/html
COPY apps/dashboard/nginx.conf /etc/nginx/conf.d/default.conf
EXPOSE 80
```

### `apps/dashboard/nginx.conf`

```nginx
server {
    listen 80;
    root /usr/share/nginx/html;
    index index.html;

    location /api/ {
        proxy_pass http://api:8000/;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }

    location / {
        try_files $uri $uri/ /index.html;
    }
}
```

---

## `docker-compose.local.yml`

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
      retries: 10

  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 5s
      timeout: 3s
      retries: 5

  servicebus-emulator:
    image: mcr.microsoft.com/azure-messaging/servicebus-emulator:latest
    ports:
      - "5672:5672"
    environment:
      ACCEPT_EULA: "Y"
    healthcheck:
      test: ["CMD-SHELL", "curl -sf http://localhost:5672/ || exit 1"]
      interval: 10s
      timeout: 5s
      retries: 10

  api:
    build:
      context: .
      dockerfile: apps/api/Dockerfile
    ports:
      - "8000:8000"
    environment:
      APP_ENV: local
      POSTGRES_HOST: postgres
      POSTGRES_PORT: 5432
      POSTGRES_DB: remediai
      POSTGRES_USER: remediai
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD:-change_me_locally}
      REDIS_URL: redis://redis:6379/0
      AZURE_SERVICEBUS_NAMESPACE: ${AZURE_SERVICEBUS_NAMESPACE:-localhost}
      AZURE_OPENAI_ENDPOINT: ${AZURE_OPENAI_ENDPOINT:-}
      AZURE_OPENAI_DEPLOYMENT: ${AZURE_OPENAI_DEPLOYMENT:-gpt-4o}
    depends_on:
      postgres:
        condition: service_healthy
      redis:
        condition: service_healthy
    healthcheck:
      test: ["CMD-SHELL", "curl -sf http://localhost:8000/health || exit 1"]
      interval: 10s
      timeout: 5s
      retries: 10

  worker:
    build:
      context: .
      dockerfile: apps/worker/Dockerfile
    environment:
      APP_ENV: local
      POSTGRES_HOST: postgres
      POSTGRES_DB: remediai
      POSTGRES_USER: remediai
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD:-change_me_locally}
      REDIS_URL: redis://redis:6379/0
      AZURE_SERVICEBUS_NAMESPACE: ${AZURE_SERVICEBUS_NAMESPACE:-localhost}
      AZURE_OPENAI_ENDPOINT: ${AZURE_OPENAI_ENDPOINT:-}
      AZURE_DEVOPS_ORG_URL: ${AZURE_DEVOPS_ORG_URL:-}
      AZURE_DEVOPS_PROJECT: ${AZURE_DEVOPS_PROJECT:-}
      AZURE_DEVOPS_PAT: ${AZURE_DEVOPS_PAT:-}
      AZURE_SEARCH_ENDPOINT: ${AZURE_SEARCH_ENDPOINT:-}
    depends_on:
      postgres:
        condition: service_healthy
      servicebus-emulator:
        condition: service_healthy

  dashboard:
    build:
      context: .
      dockerfile: apps/dashboard/Dockerfile
    ports:
      - "3000:80"
    depends_on:
      api:
        condition: service_healthy

volumes:
  postgres_data:
```

---

## `.env.local.example`

```dotenv
# Postgres — no change required for local
POSTGRES_PASSWORD=change_me_locally

# Azure OpenAI — required for agent pipeline to run (use a non-prod deployment)
AZURE_OPENAI_ENDPOINT=https://your-openai.openai.azure.com/
AZURE_OPENAI_DEPLOYMENT=gpt-4o

# Azure DevOps — required for bug creation and code context
AZURE_DEVOPS_ORG_URL=https://dev.azure.com/your-org
AZURE_DEVOPS_PROJECT=your-project
AZURE_DEVOPS_PAT=your-pat-token

# Azure AI Search — required for RAG retrieval
AZURE_SEARCH_ENDPOINT=https://your-search.search.windows.net

# Optional: Service Bus (defaults to emulator in local stack)
AZURE_SERVICEBUS_NAMESPACE=localhost
```

---

## Makefile Additions

```makefile
local-up:
    cp -n .env.local.example .env.local || true
    docker compose -f docker-compose.local.yml --env-file .env.local up --build -d

local-down:
    docker compose -f docker-compose.local.yml down

local-logs:
    docker compose -f docker-compose.local.yml logs -f

local-migrate:
    docker compose -f docker-compose.local.yml exec api alembic upgrade head
```

---

## First-Run Workflow

```
1. cp .env.local.example .env.local
2. Fill in AZURE_OPENAI_ENDPOINT and AZURE_DEVOPS_PAT in .env.local
3. make local-up          # builds images and starts all containers (~2 min first run)
4. make local-migrate     # runs Alembic migrations against the local Postgres
5. Open http://localhost:3000  → React dashboard loads
6. Open http://localhost:8000/health → {"status": "ok"}
7. Open http://localhost:8000/docs  → FastAPI Swagger UI
```

---

## Acceptance Criteria

- `docker compose -f docker-compose.local.yml config` validates without errors.
- `make local-up` starts all 5 services with no manual steps beyond `.env.local`.
- `http://localhost:3000` opens the React dashboard in a browser.
- `http://localhost:8000/health` returns `{"status": "ok"}`.
- `http://localhost:8000/docs` renders the FastAPI OpenAPI UI.
- `make local-migrate` applies all Alembic migrations against the local Postgres.
- `POST http://localhost:8000/api/v1/incidents` (test payload) creates an incident record.
- All three `docker build` commands succeed independently.
- Images do not contain dev dependencies (multi-stage build verified).
- `docker compose -f docker-compose.local.yml down -v` cleans up all volumes cleanly.

---

## Out of Scope

- Azure Managed Identity / Key Vault (production only — Phase 24).
- TLS/HTTPS locally (plain HTTP is sufficient for local dev).
- Production Helm chart values (Phase 23).
- Running the full agent pipeline with real Azure services (requires real
  credentials in `.env.local`; the stack starts and is browser-testable
  without them).
