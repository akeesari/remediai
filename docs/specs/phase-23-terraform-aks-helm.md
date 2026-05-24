# Phase 23 — Terraform Infrastructure + AKS Deployment + Helm Charts

## Goal

Provision all Azure resources using Terraform, then package all services as
Helm charts deployable to AKS.  At the end of this phase a single
`terraform apply` followed by `helm-deploy` brings up a fully operational
RemediAI environment in production.

These were originally separate phases (Terraform IaC and AKS/Helm) but are
merged here because the Helm deploy is blocked on Terraform outputs, and
splitting them would require a partial-infrastructure handoff with no
working system at the boundary.

---

## Background

This phase fills the gap between "Docker images pushed to ACR by CI" (Phase 21)
and a running production system.  Helm charts reuse the Dockerfiles created in
Phase 20 (Local Docker Compose) without modification.

---

## Deliverables

### Terraform Infrastructure

| Artifact | Description |
|---|---|
| `infrastructure/terraform/main.tf` | Root module — calls all child modules |
| `infrastructure/terraform/variables.tf` | Input variables: region, prefix, SKUs |
| `infrastructure/terraform/outputs.tf` | Output values consumed by Helm values |
| `infrastructure/terraform/terraform.tfvars.example` | Example variable values |
| `infrastructure/terraform/modules/aks/` | AKS cluster + node pools |
| `infrastructure/terraform/modules/acr/` | Azure Container Registry |
| `infrastructure/terraform/modules/postgresql/` | Azure Database for PostgreSQL Flexible Server |
| `infrastructure/terraform/modules/servicebus/` | Service Bus namespace + topic + subscription |
| `infrastructure/terraform/modules/keyvault/` | Key Vault + access policies |
| `infrastructure/terraform/modules/aisearch/` | Azure AI Search service + index |
| `infrastructure/terraform/modules/storage/` | Azure Blob Storage account |
| `infrastructure/terraform/modules/monitoring/` | Log Analytics workspace + Application Insights |
| `infrastructure/terraform/modules/network/` | VNet, subnets, private endpoints |
| `Makefile` update | `tf-init`, `tf-plan`, `tf-apply`, `tf-destroy` targets |

### Helm Charts

| Artifact | Description |
|---|---|
| `helm/remediai/Chart.yaml` | Parent Helm chart metadata |
| `helm/remediai/values.yaml` | Default values (images, replicas, resources) |
| `helm/remediai/values-prod.yaml` | Production overrides |
| `helm/remediai/templates/api/` | API Deployment, Service, HPA |
| `helm/remediai/templates/worker-agents/` | Agent Worker Deployment |
| `helm/remediai/templates/worker-ingestion/` | Ingestion Worker CronJob |
| `helm/remediai/templates/dashboard/` | Dashboard Deployment + Service + Ingress |
| `helm/remediai/templates/configmap.yaml` | Non-secret configuration |
| `helm/remediai/templates/serviceaccount.yaml` | ServiceAccount with Workload Identity annotation |
| `helm/remediai/templates/networkpolicy.yaml` | NetworkPolicy: ingress/egress rules per service |
| `Makefile` update | `helm-lint`, `helm-dry-run`, `helm-deploy` targets |

---

## Azure Resources Provisioned

| Resource | SKU / Config | Notes |
|---|---|---|
| AKS cluster | Standard_D4s_v3 × 2 system nodes | Workload Identity + OIDC issuer enabled |
| AKS node pool (agent workers) | Standard_D4s_v3 × 1–4 | Autoscales via KEDA (Phase 24) |
| Azure Container Registry | Basic/Standard | Admin disabled; AcrPull granted to AKS identity |
| PostgreSQL Flexible Server | Standard_D2s_v3, 32 GB | Private endpoint; no public access |
| Redis Cache | C1/C2 | Private endpoint |
| Service Bus namespace | Standard | Topic `incident-events` + subscription `agent-worker` |
| Key Vault | Standard | Soft-delete + purge protection enabled |
| Azure AI Search | Basic/Standard S1 | Semantic search enabled |
| Blob Storage | StorageV2 LRS | Container `evidence`; lifecycle: delete after 365 days |
| Log Analytics workspace | PerGB2018 | 90-day retention |
| Application Insights | workspace-based | Linked to Log Analytics |
| VNet + subnets | /16 VNet, /24 per service | |
| Private endpoints | PostgreSQL, Redis, Key Vault, Service Bus, Storage | |

---

## Terraform Root Module Skeleton

```hcl
terraform {
  required_version = ">= 1.8"
  required_providers {
    azurerm = {
      source  = "hashicorp/azurerm"
      version = "~> 3.110"
    }
  }
  backend "azurerm" {
    resource_group_name  = "remediai-tfstate-rg"
    storage_account_name = "remediaitfstate"
    container_name       = "tfstate"
    key                  = "remediai.tfstate"
  }
}

module "network"    { source = "./modules/network"    ... }
module "acr"        { source = "./modules/acr"        ... }
module "aks"        { source = "./modules/aks"        ... }
module "postgresql" { source = "./modules/postgresql" ... }
module "servicebus" { source = "./modules/servicebus" ... }
module "keyvault"   { source = "./modules/keyvault"   ... }
module "aisearch"   { source = "./modules/aisearch"   ... }
module "storage"    { source = "./modules/storage"    ... }
module "monitoring" { source = "./modules/monitoring" ... }
```

### Key Variables

```hcl
variable "location"       { type = string default = "australiaeast" }
variable "prefix"         { type = string default = "remediai" }
variable "environment"    { type = string default = "dev" }
variable "aks_node_count" { type = number default = 2 }
variable "aks_vm_size"    { type = string default = "Standard_D4s_v3" }
variable "postgres_sku"   { type = string default = "Standard_D2s_v3" }
```

### Key Outputs

```hcl
output "aks_cluster_name"           { value = module.aks.cluster_name }
output "acr_login_server"           { value = module.acr.login_server }
output "keyvault_uri"               { value = module.keyvault.vault_uri }
output "postgres_fqdn"              { value = module.postgresql.fqdn }
output "servicebus_namespace_fqdn"  { value = module.servicebus.namespace_fqdn }
output "aisearch_endpoint"          { value = module.aisearch.endpoint }
output "log_analytics_workspace_id" { value = module.monitoring.workspace_id }
```

---

## AKS Module Requirements

- Kubernetes version: `1.30` (latest stable).
- System node pool: `Standard_D4s_v3 × 2`, OS disk 128 GB, ephemeral.
- Agent node pool: `Standard_D4s_v3 × 1`, autoscale min 1 / max 4.
- OIDC issuer URL enabled (required for Workload Identity in Phase 24).
- Workload Identity add-on enabled.
- Azure CNI networking; private cluster.
- Container Insights linked to Log Analytics.

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

### Key `values.yaml` Sections

```yaml
global:
  registry: remediai.azurecr.io
  imageTag: latest

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
```

---

## Kubernetes Resources

### API Deployment

- `livenessProbe`: `GET /health` every 10s, failure threshold 3.
- `readinessProbe`: `GET /health` every 5s, failure threshold 2.
- `HorizontalPodAutoscaler`: min 2, max 10, CPU target 70%.

### Agent Worker Deployment

- No HPA — KEDA controls scaling in Phase 24.
- `terminationGracePeriodSeconds: 120`.

### Ingestion Worker CronJob

- `concurrencyPolicy: Forbid`.
- `successfulJobsHistoryLimit: 3`, `failedJobsHistoryLimit: 5`.

### Dashboard Ingress

- Ingress class: `azure/application-gateway`.
- WAF policy annotation referencing OWASP 3.2 policy.

---

## Network Policies

```yaml
# Agent Worker: deny all ingress; allow egress to PostgreSQL, Service Bus, ADO, AI Search, OpenAI only
# API:          allow ingress from Ingress Controller on port 8000; egress to PostgreSQL only
# Dashboard:    allow ingress from Ingress Controller on port 80; no backend egress
```

---

## Makefile Additions

```makefile
tf-init:
    terraform -chdir=infrastructure/terraform init

tf-plan:
    terraform -chdir=infrastructure/terraform plan -var-file=terraform.tfvars

tf-apply:
    terraform -chdir=infrastructure/terraform apply -var-file=terraform.tfvars

tf-destroy:
    terraform -chdir=infrastructure/terraform destroy -var-file=terraform.tfvars

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

## Security Requirements

- No credentials in `.tf` files or state — all secrets written to Key Vault.
- AKS uses Workload Identity (no stored credentials in the cluster).
- PostgreSQL, Redis have no public endpoints.
- ACR admin disabled; AKS identity uses `AcrPull` role assignment.
- Key Vault purge protection and soft-delete enabled.
- Terraform service principal: `Contributor` on the resource group,
  `Key Vault Administrator` on the Key Vault.
- No development dependencies in production images (multi-stage builds).

---

## Acceptance Criteria

- `terraform validate` passes with no errors.
- `terraform plan` produces a clean plan against a target subscription.
- `terraform apply` completes and all resources exist in Azure.
- Outputs from `outputs.tf` are sufficient to populate `values-prod.yaml`.
- `helm lint helm/remediai/` passes with no errors or warnings.
- `helm template helm/remediai/` renders valid YAML for all templates.
- `helm-dry-run` with a populated `values-prod.yaml` renders all resources.
- NetworkPolicy templates correctly restrict inter-service communication.
- AKS cluster is reachable via `kubectl`.
- `terraform destroy` cleanly removes all resources.

---

## Out of Scope

- Workload Identity pod binding (Phase 24).
- KEDA ScaledObject definitions (Phase 24).
- TLS certificate provisioning (cert-manager assumed managed externally).
- Multi-region or disaster recovery configuration.
