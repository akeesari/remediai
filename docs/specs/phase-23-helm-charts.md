# Phase 23 — Helm Chart Creation and Deployment

## Goal

Package all RemediAI services as Helm charts and deploy them to an existing AKS
cluster. At the end of this phase a single `helm-deploy` command brings up a
fully operational RemediAI environment against pre-provisioned Azure
infrastructure.

---

## Background

This phase assumes all Azure resources (AKS, ACR, PostgreSQL, Key Vault, AI
Search, Blob Storage, etc.) are already provisioned and accessible. Docker images
are pushed to ACR by CI (Phase 21). Helm charts reference those images without
modifying Dockerfiles created in Phase 20.

> **Note (post-Phase 31):** Azure Service Bus was removed as a runtime dependency
> to enable cloud-agnostic distribution via Artifact Hub. The Helm chart requires
> no Service Bus namespace. KEDA autoscaling (Phase 24) uses a PostgreSQL scaler
> (`SELECT COUNT(*) FROM incidents WHERE status = 'new'`) instead of a Service Bus
> queue depth trigger.

---

## Prerequisites

The following must be available before starting this phase:

| Requirement | Notes |
|---|---|
| AKS cluster | `kubectl` context configured and reachable |
| ACR login server | e.g. `remediai.azurecr.io` |
| PostgreSQL FQDN | e.g. `remediai-pg.postgres.database.azure.com` |
| Key Vault URI | e.g. `https://remediai-kv.vault.azure.net/` |
| AI Search endpoint | e.g. `https://remediai-search.search.windows.net` |
| Workload Identity client ID | Managed identity for AKS pods |
| `helm` ≥ 3.14 installed | On the machine or CI runner running the deploy |

---

## Deliverables

| Artifact | Description |
|---|---|
| `helm/remediai/Chart.yaml` | Parent chart metadata |
| `helm/remediai/values.yaml` | Default values (images, replicas, resources) |
| `helm/remediai/values-prod.yaml` | Production overrides — populated from existing infra |
| `helm/remediai/templates/_helpers.tpl` | Common label/name helpers |
| `helm/remediai/templates/configmap.yaml` | Non-secret configuration |
| `helm/remediai/templates/serviceaccount.yaml` | ServiceAccount with Workload Identity annotation |
| `helm/remediai/templates/networkpolicy.yaml` | NetworkPolicy: ingress/egress rules per service |
| `helm/remediai/templates/api/deployment.yaml` | API Deployment |
| `helm/remediai/templates/api/service.yaml` | API ClusterIP Service |
| `helm/remediai/templates/api/hpa.yaml` | HorizontalPodAutoscaler |
| `helm/remediai/templates/worker-agents/deployment.yaml` | Agent Worker Deployment |
| `helm/remediai/templates/worker-ingestion/cronjob.yaml` | Ingestion Worker CronJob |
| `helm/remediai/templates/dashboard/deployment.yaml` | Dashboard Deployment |
| `helm/remediai/templates/dashboard/service.yaml` | Dashboard Service |
| `helm/remediai/templates/dashboard/ingress.yaml` | Dashboard Ingress (AGIC) |
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

## Chart.yaml

```yaml
apiVersion: v2
name: remediai
description: RemediAI — AI-powered incident triage and remediation platform
type: application
version: 0.1.0
appVersion: "0.1.0"
```

---

## values.yaml

```yaml
global:
  registry: remediai.azurecr.io
  imageTag: latest
  workloadIdentityClientId: ""

api:
  image: remediai/api
  replicas: 2
  resources:
    requests: { cpu: 250m, memory: 256Mi }
    limits:   { cpu: 500m, memory: 512Mi }
  port: 8000

workerAgents:
  image: remediai/worker
  replicas: 1               # KEDA manages scaling in Phase 24

workerIngestion:
  image: remediai/worker
  schedule: "*/5 * * * *"

dashboard:
  image: remediai/dashboard
  replicas: 1
  port: 80
  ingress:
    enabled: true
    host: remediai.example.com
    tlsSecretName: remediai-tls

config:
  postgresFqdn: ""
  keyVaultUri: ""
  aiSearchEndpoint: ""
```

---

## values-prod.yaml (populated from existing infra)

```yaml
global:
  registry: <acr-login-server>
  imageTag: <git-sha>
  workloadIdentityClientId: <managed-identity-client-id>

config:
  postgresFqdn: <postgres-fqdn>
  keyVaultUri: <keyvault-uri>
  aiSearchEndpoint: <aisearch-endpoint>

dashboard:
  ingress:
    host: <actual-dns-name>
    tlsSecretName: remediai-tls
```

---

## Kubernetes Resources

### API Deployment

- `livenessProbe`: `GET /health` every 10s, failure threshold 3.
- `readinessProbe`: `GET /health` every 5s, failure threshold 2.
- Env vars sourced from ConfigMap; secrets sourced from Key Vault via Workload Identity.

### HorizontalPodAutoscaler (API)

- Min replicas: 2, max: 10.
- CPU target: 70%.

### Agent Worker Deployment

- No HPA — KEDA controls scaling in Phase 24.
- `terminationGracePeriodSeconds: 120`.

### Ingestion Worker CronJob

- `concurrencyPolicy: Forbid`.
- `successfulJobsHistoryLimit: 3`, `failedJobsHistoryLimit: 5`.

### ServiceAccount

- Annotated with `azure.workload.identity/client-id` from `global.workloadIdentityClientId`.
- Bound to the managed identity that has Key Vault Secrets User + other required roles.

### Dashboard Ingress

- Ingress class: `azure/application-gateway`.
- WAF policy annotation referencing OWASP 3.2 policy.
- TLS secret referenced by `dashboard.ingress.tlsSecretName`.

---

## Network Policies

```yaml
# Agent Worker: deny all ingress; allow egress to PostgreSQL, AI Search,
#               OpenAI, Key Vault only (port 5432 + 443)
# API:          allow ingress from Ingress Controller on port 8000;
#               egress to PostgreSQL and Key Vault only
# Dashboard:    allow ingress from Ingress Controller on port 80;
#               no backend egress
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

helm-uninstall:
	helm uninstall remediai --namespace remediai
```

---

## Security Requirements

- No credentials stored in chart files or values files — all secrets come from Key Vault via Workload Identity.
- `values-prod.yaml` must not be committed with real values; `.gitignore` it or use a secrets manager in CI.
- NetworkPolicy templates restrict inter-service communication to the minimum required.
- ACR pull access granted to the AKS kubelet identity (`AcrPull` role) — no registry credentials in the cluster.
- Workload Identity used for all Azure SDK calls inside pods — no stored credentials.

---

## Deployment Process

1. **Configure kubectl context**
   ```bash
   az aks get-credentials --resource-group <rg> --name <cluster-name>
   ```

2. **Populate `values-prod.yaml`** from existing infrastructure outputs
   (ACR login server, PostgreSQL FQDN, Key Vault URI, AI Search endpoint, managed identity client ID).

3. **Lint the chart**
   ```bash
   make helm-lint
   ```

4. **Dry-run to verify rendered manifests**
   ```bash
   make helm-dry-run
   ```

5. **Deploy**
   ```bash
   GIT_SHA=$(git rev-parse --short HEAD) make helm-deploy
   ```

6. **Verify**
   ```bash
   kubectl get pods -n remediai
   kubectl get ingress -n remediai
   ```

---

## Acceptance Criteria

- `helm lint helm/remediai/` passes with no errors or warnings.
- `helm template helm/remediai/` renders valid YAML for all templates.
- `helm-dry-run` with a populated `values-prod.yaml` renders all resources without errors.
- `helm-deploy` succeeds and all pods reach `Running` status.
- API `/health` endpoint responds `200 OK` through the Ingress.
- Dashboard is reachable at the configured hostname.
- NetworkPolicy templates correctly restrict inter-service communication.
- No credentials appear in any chart file or rendered manifest.

---

## Out of Scope

- Azure infrastructure provisioning (assumed pre-existing).
- Terraform IaC (not part of this project).
- Workload Identity pod binding setup (Phase 24).
- KEDA ScaledObject definitions (Phase 24).
- TLS certificate provisioning (cert-manager assumed managed externally).
- Multi-region or disaster recovery configuration.
