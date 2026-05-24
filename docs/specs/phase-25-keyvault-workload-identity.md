# Phase 25 — Key Vault + Workload Identity

## Goal

Replace all hardcoded secrets and environment-variable-injected credentials
with Azure Key Vault secrets mounted via the Secrets Store CSI Driver, and
configure Workload Identity Federation so every AKS pod authenticates to
Azure services without a client secret or certificate.

---

## Background

SECURITY_GUARDRAILS.md requires:
- All secrets in Azure Key Vault.
- Secrets mounted via CSI Driver (no raw environment variable injection).
- Managed Identity / Workload Identity — no stored credentials in the cluster.

The current local dev configuration uses `.env` files.  This phase defines
the production secret management architecture and the Terraform resources.

---

## Deliverables

| Artifact | Description |
|---|---|
| `infra/terraform/modules/keyvault/main.tf` | Key Vault resource, access policies, private endpoint |
| `infra/terraform/modules/workload-identity/main.tf` | Managed Identity, Federated Identity Credential, role assignments |
| `infra/terraform/environments/prod/main.tf` | Root module wiring all sub-modules |
| `infra/terraform/environments/prod/variables.tf` | Input variables |
| `infra/terraform/environments/prod/outputs.tf` | Output values (client IDs, vault URI) |
| `helm/remediai/templates/secretproviderclass.yaml` | `SecretProviderClass` for each service |
| Updated `helm/remediai/templates/serviceaccount.yaml` | Workload Identity annotations |
| Updated `helm/remediai/values.yaml` | `workloadIdentity.clientId` and `workloadIdentity.tenantId` |
| `docs/runbooks/keyvault-rotation.md` | Runbook for secret rotation |

---

## Key Vault Secrets

| Secret Name | Consumed by | Description |
|---|---|---|
| `postgres-connection-string` | API, Agent Worker | PostgreSQL connection string with credentials |
| `azure-openai-api-key` | Agent Worker | Azure OpenAI API key (fallback if Managed Identity not available) |
| `azure-devops-pat` | Agent Worker | ADO Personal Access Token |
| `azure-search-api-key` | Agent Worker | Azure AI Search admin key (fallback) |
| `applicationinsights-connection-string` | All services | App Insights connection string |
| `servicebus-connection-string` | Ingestion Worker, Agent Worker | Service Bus connection string (fallback) |
| `redis-connection-string` | API | Redis connection string |

In production, Azure OpenAI, AI Search, and Service Bus are accessed via
Managed Identity — the API keys are stored as fallbacks for non-MI environments
(e.g., development against shared resources).

---

## Workload Identity Architecture

```
AKS Pod
  └── Kubernetes ServiceAccount (annotated with MI client ID)
        └── Federated Identity Credential → Azure Managed Identity
              └── Role Assignments:
                    Key Vault Secrets User
                    Monitoring Reader
                    Service Bus Data Receiver/Sender
                    Cognitive Services OpenAI User
                    Search Index Data Reader
                    Storage Blob Data Contributor
```

One Managed Identity per service (API, Agent Worker, Ingestion Worker) with
the minimum required role assignments.

---

## Terraform Modules

### `modules/keyvault/main.tf`

Resources:
- `azurerm_key_vault` — soft-delete enabled, purge protection enabled, RBAC auth model.
- `azurerm_private_endpoint` — Key Vault private endpoint in the AKS subnet.
- `azurerm_key_vault_secret` — Placeholder secrets (values provided via Terraform variables or pipeline variable group, never committed).

### `modules/workload-identity/main.tf`

Resources:
- `azurerm_user_assigned_identity` — one per service.
- `azurerm_federated_identity_credential` — bound to AKS OIDC issuer URL + Kubernetes service account namespace/name.
- `azurerm_role_assignment` — granular role assignments per identity.

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
          objectName: postgres-connection-string
          objectType: secret
        - |
          objectName: applicationinsights-connection-string
          objectType: secret
  secretObjects:
    - secretName: remediai-api-secrets
      type: Opaque
      data:
        - objectName: postgres-connection-string
          key: DATABASE_URL
        - objectName: applicationinsights-connection-string
          key: APPLICATIONINSIGHTS_CONNECTION_STRING
```

Secrets are mounted as a volume and exposed as environment variables via
`secretObjects` — this is the CSI Driver approach (not raw `env` injection
of Key Vault references).

---

## Application Config Changes

`packages/config/settings.py` uses `pydantic-settings` which reads from
environment variables.  No code changes are needed; the `SecretProviderClass`
`secretObjects` section exposes Key Vault secrets as environment variables
with the exact names that `pydantic-settings` expects.

---

## Secret Rotation Runbook (`docs/runbooks/keyvault-rotation.md`)

Covers:
1. How to rotate the ADO PAT (generate new PAT in ADO → update Key Vault secret → pods pick up on next mount refresh).
2. How to rotate the PostgreSQL password (Alembic-safe rotation: dual credentials, update Key Vault, restart pods, remove old credential).
3. Key Vault soft-delete recovery procedure.

---

## Acceptance Criteria

- `terraform validate` passes on all modules.
- `terraform plan` produces the expected resource set with no unexpected deletions.
- AKS pods start and reach `Running` state with secrets mounted.
- No secrets appear in Kubernetes `Secret` objects created outside the CSI Driver flow.
- `kubectl exec` into a pod shows the expected environment variables populated from Key Vault.
- `detect-secrets scan` finds no secrets in the Terraform files (all values are variables).

---

## Out of Scope

- Terraform state backend configuration (assumed pre-existing Azure Storage Account).
- AKS cluster provisioning (assumed pre-existing or provisioned separately).
- Certificate management (cert-manager assumed installed on the cluster).
- Key Vault firewall / IP allow-listing (handled at network layer).
