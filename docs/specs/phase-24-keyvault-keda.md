# Phase 24 — Key Vault + Workload Identity + KEDA Autoscaling

## Goal

Replace all environment-variable-injected credentials with Azure Key Vault
secrets mounted via the Secrets Store CSI Driver, configure Workload Identity
Federation for every AKS pod, and add KEDA autoscaling for the Agent Worker
and Ingestion Worker.

These were originally separate phases but are merged here because KEDA's
`TriggerAuthentication` requires Workload Identity — neither is independently
shippable without the other.

---

## Background

SECURITY_GUARDRAILS.md requires:
- All secrets in Azure Key Vault; mounted via CSI Driver (no raw env injection).
- Managed Identity / Workload Identity — no stored credentials in the cluster.

ARCHITECTURE.md lists KEDA as the autoscaling mechanism.  The Agent Worker
currently runs as a fixed single-replica deployment (Phase 23).

---

## Deliverables

### Key Vault + Workload Identity

| Artifact | Description |
|---|---|
| `infrastructure/terraform/modules/keyvault/main.tf` | Key Vault resource, RBAC, private endpoint |
| `infrastructure/terraform/modules/workload-identity/main.tf` | Managed Identity, Federated Identity Credential, role assignments |
| `helm/remediai/templates/secretproviderclass.yaml` | `SecretProviderClass` for each service |
| Updated `helm/remediai/templates/serviceaccount.yaml` | Workload Identity annotations |
| Updated `helm/remediai/values.yaml` | `workloadIdentity.clientId` and `.tenantId` |
| `docs/runbooks/keyvault-rotation.md` | Secret rotation runbook |

### KEDA Autoscaling

| Artifact | Description |
|---|---|
| `helm/remediai/templates/worker-agents/scaledobject.yaml` | KEDA `ScaledObject` for Agent Worker (PostgreSQL trigger) |
| `helm/remediai/templates/worker-ingestion/scaledjob.yaml` | KEDA `ScaledJob` for Ingestion Worker (cron trigger) |
| Updated `helm/remediai/values.yaml` | KEDA scaling parameters |
| `docs/runbooks/keda-scaling.md` | Runbook: tuning thresholds, disabling scaling |

---

## Key Vault Secrets

| Secret Name | Consumed by | Description |
|---|---|---|
| `postgres-password` | API, Agent Worker | Password for the in-cluster PostgreSQL service |
| `redis-password` | API | Password for the in-cluster Redis service |
| `azure-openai-api-key` | Agent Worker | Azure OpenAI API key (fallback for non-MI) |
| `azure-devops-pat` | Agent Worker | ADO Personal Access Token |
| `azure-search-api-key` | Agent Worker | Azure AI Search admin key (fallback) |
| `applicationinsights-connection-string` | All services | App Insights connection string |

In production, Azure OpenAI, AI Search, and Service Bus are accessed via
Managed Identity — the API keys are stored as fallbacks for non-MI environments.

---

## Workload Identity Architecture

```
AKS Pod
  └── Kubernetes ServiceAccount (annotated with MI client ID)
        └── Federated Identity Credential → Azure Managed Identity
              └── Role Assignments:
                    Key Vault Secrets User
                    Monitoring Reader
                    Cognitive Services OpenAI User
                    Search Index Data Reader
                    Storage Blob Data Contributor
```

One Managed Identity per service (API, Agent Worker, Ingestion Worker).

---

## Terraform Modules

### `modules/keyvault/main.tf`

- `azurerm_key_vault` — soft-delete enabled, purge protection, RBAC auth.
- `azurerm_private_endpoint` — in the AKS subnet.
- `azurerm_key_vault_secret` — placeholder secrets; values via pipeline variables.

### `modules/workload-identity/main.tf`

- `azurerm_user_assigned_identity` — one per service.
- `azurerm_federated_identity_credential` — bound to AKS OIDC issuer + SA.
- `azurerm_role_assignment` — granular per identity.

---

## `SecretProviderClass` (per service)

```yaml
apiVersion: secrets-store.csi.x-k8s.io/v1
kind: SecretProviderClass
metadata:
  name: remediai-api-secrets
spec:
  provider: azure
  parameters:
    usePodIdentity: "false"
    clientID: {{ .Values.workloadIdentity.clientId }}
    keyvaultName: {{ .Values.keyvault.name }}
    tenantID: {{ .Values.workloadIdentity.tenantId }}
    objects: |
      array:
        - |
          objectName: postgres-password
          objectType: secret
        - |
          objectName: applicationinsights-connection-string
          objectType: secret
        - |
          objectName: redis-password
          objectType: secret
  secretObjects:
    - secretName: remediai-api-secrets
      type: Opaque
      data:
        - objectName: postgres-password
          key: POSTGRES_PASSWORD
        - objectName: redis-password
          key: REDIS_PASSWORD
        - objectName: applicationinsights-connection-string
          key: APPLICATIONINSIGHTS_CONNECTION_STRING
```

---

## KEDA — Agent Worker `ScaledObject`

```yaml
apiVersion: keda.sh/v1alpha1
kind: ScaledObject
metadata:
  name: remediai-agent-worker
spec:
  scaleTargetRef:
    name: remediai-worker-agents
  minReplicaCount: 1
  maxReplicaCount: 10
  cooldownPeriod: 60
  pollingInterval: 15
  triggers:
    - type: postgresql
      metadata:
        host: "${POSTGRES_HOST}"
        port: "5432"
        dbName: "remediai"
        userName: "${POSTGRES_USER}"
        passwordFromEnv: POSTGRES_PASSWORD
        sslmode: require
        query: "SELECT COUNT(*) FROM incidents WHERE status = 'new'"
        targetQueryValue: "5"
        activationTargetQueryValue: "1"
```

**Scaling logic:** 1 replica per 5 queued incidents in PostgreSQL (`status='new'`);
minimum 1 (no scale-to-zero — cold start would exceed the 3-minute SLA);
maximum 10 respects Azure OpenAI rate limits.

---

## KEDA — Ingestion Worker `ScaledJob`

```yaml
apiVersion: keda.sh/v1alpha1
kind: ScaledJob
metadata:
  name: remediai-ingestion-worker
spec:
  jobTargetRef:
    template:
      spec:
        containers:
          - name: ingestion-worker
            image: {{ .Values.workerIngestion.image }}:{{ .Values.global.imageTag }}
  triggers:
    - type: cron
      metadata:
        timezone: UTC
        start: "*/5 * * * *"
        end:   "*/5 * * * *"
        desiredReplicas: "1"
  successfulJobsHistoryLimit: 3
  failedJobsHistoryLimit: 5
```

---

## `values.yaml` Additions

```yaml
keda:
  agentWorker:
    minReplicas: 1
    maxReplicas: 10
    targetQueryValue: 5
    activationTargetQueryValue: 1
    cooldownPeriod: 60
    pollingInterval: 15
    query: "SELECT COUNT(*) FROM incidents WHERE status = 'new'"
  ingestionWorker:
    cronSchedule: "*/5 * * * *"
    timezone: UTC
```

---

## Runbooks

### `docs/runbooks/keyvault-rotation.md`

1. Rotating ADO PAT (generate → update Key Vault → pods pick up on next mount).
2. Rotating PostgreSQL password (dual credentials → update Key Vault → restart pods → remove old).
3. Key Vault soft-delete recovery.

### `docs/runbooks/keda-scaling.md`

1. Check current replica count and queue depth.
2. Temporarily pause autoscaling (`minReplicas = maxReplicas = N`).
3. Tune `messageCountPerReplica` without a full deploy.
4. Diagnose `ScaledObject` errors (`kubectl describe scaledobject`).

---

## Acceptance Criteria

- `terraform validate` passes on all Workload Identity modules.
- AKS pods start in `Running` state with secrets mounted from Key Vault.
- No secrets appear in Kubernetes `Secret` objects outside the CSI Driver flow.
- `kubectl exec` shows expected environment variables populated from Key Vault.
- `detect-secrets scan` finds no secrets in Terraform files.
- `helm lint` passes with KEDA templates included.
- API and worker resolve PostgreSQL and Redis through in-cluster DNS names rather than Azure managed service endpoints.
- Queue depth of 15 `new` incidents → 3 agent worker replicas (staging verification).
- Queue drained → replicas return to 1 within `cooldownPeriod`.
- Ingestion worker runs once per 5-minute interval.
- `ScaledObject` uses PostgreSQL scaler query with no Service Bus trigger.

---

## Out of Scope

- KEDA operator installation (assumed installed via Helm add-on on the AKS cluster).
- Azure OpenAI deployment scaling or model quota management.
- Prometheus-based scaling triggers.
- cert-manager and TLS certificate issuance.
- Key Vault firewall / IP allow-listing (handled at network layer).
