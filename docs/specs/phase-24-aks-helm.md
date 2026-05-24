# Phase 24 — AKS Deployment + Helm Charts

## Goal

Package all three services (API, Agent Worker, Ingestion Worker) and the React
dashboard as Helm charts deployable to Azure Kubernetes Service (AKS).  Each
service has its own Deployment, Service, and HorizontalPodAutoscaler or KEDA
ScaledObject.

---

## Deliverables

| Artifact | Description |
|---|---|
| `helm/remediai/Chart.yaml` | Parent Helm chart metadata |
| `helm/remediai/values.yaml` | Default values (all images, replicas, resources) |
| `helm/remediai/values-prod.yaml` | Production overrides |
| `helm/remediai/templates/api/` | API Deployment, Service, HPA |
| `helm/remediai/templates/worker-agents/` | Agent Worker Deployment (scaled by KEDA in Phase 26) |
| `helm/remediai/templates/worker-ingestion/` | Ingestion Worker CronJob |
| `helm/remediai/templates/dashboard/` | Dashboard Deployment + Service + Ingress |
| `helm/remediai/templates/configmap.yaml` | Non-secret configuration |
| `helm/remediai/templates/serviceaccount.yaml` | Kubernetes ServiceAccount with Workload Identity annotation |
| `helm/remediai/templates/networkpolicy.yaml` | NetworkPolicy: ingress/egress rules per service |
| `Dockerfile` files | `apps/api/Dockerfile`, `apps/worker/Dockerfile`, `apps/dashboard/Dockerfile` |
| `Makefile` update | `helm-lint`, `helm-dry-run`, `helm-deploy` targets |

---

## Helm Chart Structure

```
helm/remediai/
  Chart.yaml
  values.yaml
  values-prod.yaml
  templates/
    _helpers.tpl
    configmap.yaml
    serviceaccount.yaml
    networkpolicy.yaml
    api/
      deployment.yaml
      service.yaml
      hpa.yaml
    worker-agents/
      deployment.yaml
    worker-ingestion/
      cronjob.yaml
    dashboard/
      deployment.yaml
      service.yaml
      ingress.yaml
```

---

## `values.yaml` (Key Sections)

```yaml
global:
  registry: remediai.azurecr.io
  imageTag: latest          # overridden in CI with git SHA

api:
  image: remediai/api
  replicas: 2
  resources:
    requests: { cpu: 250m, memory: 256Mi }
    limits:   { cpu: 500m, memory: 512Mi }
  port: 8000

workerAgents:
  image: remediai/worker
  replicas: 1               # KEDA manages scaling in Phase 26
  resources:
    requests: { cpu: 500m, memory: 512Mi }
    limits:   { cpu: 1000m, memory: 1Gi }

workerIngestion:
  image: remediai/worker
  schedule: "*/5 * * * *"  # Poll every 5 minutes

dashboard:
  image: remediai/dashboard
  replicas: 1
  port: 80
  ingress:
    enabled: true
    host: remediai.example.com
    tlsSecretName: remediai-tls

workloadIdentity:
  clientId: ""              # Set in values-prod.yaml
  tenantId: ""
```

---

## Dockerfiles

### `apps/api/Dockerfile`

```dockerfile
FROM python:3.12-slim AS base
WORKDIR /app
COPY pyproject.toml poetry.lock ./
RUN pip install poetry && poetry install --no-dev --no-root
COPY . .
CMD ["uvicorn", "apps.api.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

### `apps/worker/Dockerfile`

Same base as API; entrypoint is `python -m apps.worker.main`.

### `apps/dashboard/Dockerfile`

Multi-stage:
```dockerfile
FROM node:20-alpine AS build
WORKDIR /app
COPY apps/dashboard/package*.json ./
RUN npm install --legacy-peer-deps
COPY apps/dashboard/ .
RUN npm run build

FROM nginx:alpine
COPY --from=build /app/dist /usr/share/nginx/html
COPY apps/dashboard/nginx.conf /etc/nginx/conf.d/default.conf
```

---

## Kubernetes Resources

### API Deployment

- `livenessProbe`: `GET /health` every 10s, failure threshold 3.
- `readinessProbe`: `GET /health` every 5s, failure threshold 2.
- `HorizontalPodAutoscaler`: min 2, max 10, CPU target 70%.

### Agent Worker Deployment

- No HPA (KEDA controls scaling in Phase 26).
- Single replica as default; KEDA overrides at runtime.
- `terminationGracePeriodSeconds: 120` — allow in-flight pipeline runs to finish.

### Ingestion Worker CronJob

- Schedule from `values.yaml` (`*/5 * * * *`).
- `concurrencyPolicy: Forbid` — never run two ingestion jobs simultaneously.
- `successfulJobsHistoryLimit: 3`, `failedJobsHistoryLimit: 5`.

### Dashboard Ingress

- Ingress class: `azure/application-gateway`.
- TLS via certificate in `remediai-tls` secret (provisioned by cert-manager).
- WAF policy annotation referencing the OWASP 3.2 policy (as per SECURITY_GUARDRAILS).

---

## Network Policies

```yaml
# Agent Worker: deny all ingress; allow egress to PostgreSQL, Service Bus, ADO, AI Search, OpenAI endpoints only
# API:          allow ingress from Ingress Controller on port 8000; egress to PostgreSQL only
# Dashboard:    allow ingress from Ingress Controller on port 80; no backend egress
```

---

## Makefile Additions

```makefile
helm-lint:
    helm lint helm/remediai/

helm-dry-run:
    helm upgrade --install remediai helm/remediai/ \
      --values helm/remediai/values-prod.yaml \
      --dry-run --debug

helm-deploy:
    helm upgrade --install remediai helm/remediai/ \
      --values helm/remediai/values-prod.yaml \
      --set global.imageTag=$(GIT_SHA) \
      --namespace remediai --create-namespace
```

---

## Acceptance Criteria

- `helm lint helm/remediai/` passes with no errors or warnings.
- `helm template helm/remediai/` renders valid YAML for all templates.
- `docker build` succeeds for all three Dockerfiles.
- `helm-dry-run` with a populated `values-prod.yaml` renders all resources.
- NetworkPolicy templates correctly restrict inter-service communication.
- Images do not include development dependencies (multi-stage builds verified).

---

## Out of Scope

- AKS cluster provisioning (Terraform — Phase 25).
- Workload Identity binding (Phase 25).
- KEDA ScaledObject definitions (Phase 26).
- TLS certificate provisioning (assumed managed by cert-manager).
