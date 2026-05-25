# RemediAI

[![License: Apache 2.0](https://img.shields.io/badge/License-Apache_2.0-blue.svg)](LICENSE)
[![Status: Pre-release](https://img.shields.io/badge/status-pre--release-orange.svg)]()
[![PRs Welcome](https://img.shields.io/badge/PRs-welcome-brightgreen.svg)](CONTRIBUTING.md)

RemediAI is an AI-powered exception analysis and remediation platform for enterprise .NET applications on Azure.

It detects application exceptions from Azure Monitor / Application Insights, analyzes root cause using AI agents, creates remediation recommendations, and generates Azure DevOps work items and pull requests for human review.

---

## Why RemediAI?

Modern applications running on AKS, App Service, or Azure VMs generate exceptions across multiple observability platforms. Engineers spend hours triaging the same recurring patterns. RemediAI provides a scalable agentic framework to automate that investigation — so teams focus on fixing, not finding.

- Reads exception logs from Application Insights / Azure Monitor
- Groups and triages incidents automatically
- Analyzes root cause using LangGraph-based AI agents
- Finds related source code in Azure DevOps Repos
- Recommends fixes with supporting evidence
- Creates Azure DevOps Bugs with full context
- Generates draft Pull Requests after human approval
- Tracks remediation progress in a React dashboard

---

## High-Level Architecture

```mermaid
flowchart TD
    classDef azure fill:#0078D4,stroke:#005A9E,color:#fff
    classDef ai fill:#8661C5,stroke:#5C4799,color:#fff
    classDef data fill:#107C10,stroke:#054B05,color:#fff
    classDef ui fill:#00B7C3,stroke:#007A80,color:#fff
    classDef security fill:#D83B01,stroke:#A52D01,color:#fff

    A["Application Workloads<br/>AKS / App Service / VMs"]:::azure
    B["Application Insights<br/>Azure Monitor"]:::azure
    C["Log Ingestion Service<br/>Python · AKS"]:::azure
    D["Azure Service Bus<br/>incident-events"]:::azure
    E["Agent Worker<br/>Python + LangGraph"]:::ai
    F["Azure OpenAI GPT-4o"]:::ai
    G["Azure DevOps Repos"]:::azure
    H["Azure DevOps Boards"]:::azure
    I["Azure AI Search<br/>RAG Index"]:::ai
    J["PostgreSQL<br/>Incidents / Audit"]:::data
    K["Blob Storage<br/>Evidence"]:::data
    L["FastAPI Backend API"]:::azure
    M["React Dashboard"]:::ui
    N["Azure Key Vault"]:::security
    O["Managed Identity<br/>Workload Identity"]:::security

    A --> B --> C --> D --> E
    E --> F & G & H & I & J & K
    J --> L --> M
    N --> C & E & L
    O --> N
```

> **Color key:** Blue = Azure services &nbsp;·&nbsp; Purple = AI / Agent layer &nbsp;·&nbsp; Green = Data stores &nbsp;·&nbsp; Teal = UI &nbsp;·&nbsp; Red = Security

---

## Core Workflow

```
1. Exception appears in Application Insights.
2. Log ingestion service queries Azure Monitor using KQL.
3. Incident event is published to Azure Service Bus.
4. LangGraph worker picks up the incident.
5. Triage Agent assigns priority and groups related incidents.
6. Root Cause Agent analyzes the exception and stack trace.
7. Code Context Agent retrieves relevant source files.
8. RAG Agent fetches docs, runbooks, and prior fixes.
9. Fix Planner Agent produces ranked remediation recommendations.
10. Azure DevOps Bug is created with full analysis attached.
11. (Phase 2) PR Agent creates a draft pull request after human approval.
12. Dashboard shows status, metrics, and remediation progress.
```

---

## Run Locally

1. Copy local environment files:

```bash
cp .env.example .env
cp .env.local.example .env.local
```

2. Edit `.env` / `.env.local` as needed. For local startup without Azure credentials, keep Azure fields blank. To publish to a local Service Bus emulator, set `AZURE_SERVICEBUS_CONNECTION_STRING` to your emulator connection string.

3. Start the local stack:

```bash
make local-up
```

4. If you want to verify or re-run migrations:

```bash
make local-migrate
```

5. Smoke check the local stack:

```bash
make local-smoke
```

If you prefer raw Docker Compose:

```bash
docker compose -f docker-compose.local.yml --env-file .env.local up --build
```

### Local service behavior

- `http://localhost:8000/health` — API health
- `http://localhost:3000` — dashboard UI
- The worker will start and log ingestion activity; it is configured to skip Azure Monitor ingestion if `AZURE_MONITOR_WORKSPACE_ID` is not set.

---

## MVP Scope

| In Scope                              | Out of Scope                        |
| ------------------------------------- | ----------------------------------- |
| .NET application exceptions           | Auto-merge pull requests            |
| Azure Monitor / Application Insights  | Direct production changes           |
| Azure DevOps Repos + Boards           | Jira integration                    |
| Python backend + LangGraph agents     | Node.js / Java / Python app support |
| Azure AI Foundry / Azure OpenAI       | Grafana / Loki / Datadog ingestion  |
| PostgreSQL + Redis                    | Full self-healing automation        |
| React dashboard                       |                                     |

---

## Technology Stack

| Layer               | Technology                              |
| ------------------- | --------------------------------------- |
| Backend API         | Python 3.12 + FastAPI                   |
| Agent Orchestration | LangGraph                               |
| AI Platform         | Azure AI Foundry / Azure OpenAI GPT-4o  |
| RAG                 | Azure AI Search (hybrid)                |
| Log Source          | Application Insights / Azure Monitor    |
| Message Queue       | Azure Service Bus                       |
| Database            | PostgreSQL 16 (Azure Flexible Server)   |
| Cache               | Redis (Azure Cache for Redis)           |
| UI                  | React 18 + TypeScript                   |
| Hosting             | AKS (Azure Kubernetes Service)          |
| Secrets             | Azure Key Vault + Managed Identity      |
| Infrastructure      | Terraform + Helm                        |

See [TECH_STACK.md](TECH_STACK.md) for the full stack with rationale and dependency lists.

---

## Repository Structure

```
remediai/
  .github/
    copilot-instructions.md  # Repository-wide Copilot rules
    instructions/            # Scoped instruction layers by concern

  docs/
    product/          # Product briefs and discovery notes
    architecture/     # Architecture decision records (ADRs)
    specs/            # Detailed specifications
    prompts/          # Versioned LLM prompt contracts
    runbooks/         # Operational runbooks

  apps/
    api/              # FastAPI backend
    worker/           # Log ingestion + agent worker
    dashboard/        # React TypeScript frontend

  packages/
    domain/           # Shared domain models (Pydantic)
    integrations/     # Azure service clients
    agent_runtime/    # LangGraph pipeline and agent base classes
    data_access/      # SQLAlchemy models and repositories

  infrastructure/
    terraform/        # Azure resource provisioning
    helm/             # Kubernetes deployment charts
    k8s/              # Namespace, RBAC, network policy manifests

  pipelines/
    azure-devops/     # CI/CD pipeline YAML

  scripts/
    validate_prompt_contracts.py  # Prompt contract validator

  tests/
    integration/      # Integration tests (Azure mock clients)
    e2e/              # End-to-end tests
    agent-evals/      # Agent quality evaluation fixtures

  README.md
  CONTRIBUTING.md
  SECURITY.md
  SPEC.md
  ROADMAP.md
  ARCHITECTURE.md
  AGENT_DESIGN.md
  TECH_STACK.md
  SECURITY_GUARDRAILS.md
```

---

## Implementation Phases

Phases 1–21 are complete. Remaining work runs across parallel tracks.

| Track | Phases | Focus |
| ----- | ------ | ----- |
| A — Quality & Security | 15, 17, 18 | PII scrubbing, AI Search index, RAG quality |
| B — PR Workflow | 19, 20, 21 | PR agent, human approval gate, validation |
| C — DevOps & Infrastructure | 22, 23, 24, 25, 26, 27 | CI/CD, Terraform, AKS, Key Vault, scaling |
| D — Testing & Observability | 16, 23, 28 | E2E tests, OpenTelemetry, load + security testing |

Tracks A, B, C, and D can be staffed in parallel. Phase 28 (load + security
testing) is the final gate that requires all tracks to be complete.

See [ROADMAP.md](ROADMAP.md) for the full dependency graph, milestone detail, and release versioning.

---

## Build, Push, and Deploy to AKS

This repository can build three container images and deploy them to an AKS namespace.

### Build and push to Azure Container Registry

Set your registry and credentials in environment variables or GitHub/GitLab secrets.

```bash
export ACR_LOGIN_SERVER=aitenant.azurecr.io
export ACR_IMAGE_TAG=latest
export ACR_USERNAME=<service-principal-or-acr-username>
export ACR_PASSWORD=<service-principal-or-acr-password>

docker login $ACR_LOGIN_SERVER -u $ACR_USERNAME -p $ACR_PASSWORD

docker build -f apps/api/Dockerfile -t $ACR_LOGIN_SERVER/remediai-api:$ACR_IMAGE_TAG .
docker push $ACR_LOGIN_SERVER/remediai-api:$ACR_IMAGE_TAG

docker build -f apps/worker/Dockerfile -t $ACR_LOGIN_SERVER/remediai-worker:$ACR_IMAGE_TAG .
docker push $ACR_LOGIN_SERVER/remediai-worker:$ACR_IMAGE_TAG

docker build -f apps/dashboard/Dockerfile -t $ACR_LOGIN_SERVER/remediai-dashboard:$ACR_IMAGE_TAG .
docker push $ACR_LOGIN_SERVER/remediai-dashboard:$ACR_IMAGE_TAG
```

### Deploy to AKS namespace `ai`

Use Helm to deploy into the `ai` namespace after building and pushing images.

```bash
kubectl create namespace ai --dry-run=client -o yaml | kubectl apply -f -
helm upgrade --install remediai infrastructure/helm/remediai \
  --namespace ai --create-namespace \
  --set global.imageRegistry=$ACR_LOGIN_SERVER \
  --set global.imageTag=$ACR_IMAGE_TAG
```

If your cluster uses Azure credentials, run:

```bash
az login --service-principal -u "$AZURE_CLIENT_ID" -p "$AZURE_CLIENT_SECRET" --tenant "$AZURE_TENANT_ID"
az aks get-credentials --resource-group "$AKS_RESOURCE_GROUP" --name "$AKS_CLUSTER_NAME" --overwrite-existing
```

### Pipeline support

There is already a GitHub Actions workflow for GHCR in `.github/workflows/release.yml`.

This repository also now includes two pipeline skeletons:

- `.github/workflows/azure-acr-release.yml` — build and push to ACR, then deploy to AKS namespace `ai`.
- `.gitlab-ci.yml` — build, push, and deploy skeleton for GitLab CI.

Use these pipelines if you want automated image build/push and AKS deploy on every merge or tag.

> For production, keep secrets in GitHub/GitLab secret storage rather than in `.env`.

---

## Security Principles

- Human approval required before any code change is merged
- No direct production access for any agent
- Read-only access to logs and source code
- Managed Identity / Workload Identity — no stored credentials
- Azure Key Vault for all secrets
- PII scrubbed from exception payloads before LLM transmission
- Full audit trail for every agent decision
- All PRs validated before human review

See [SECURITY_GUARDRAILS.md](SECURITY_GUARDRAILS.md) for the full security design. To report a vulnerability, see [SECURITY.md](SECURITY.md).

---

## Documentation

| Document                                        | Purpose                                       |
| ----------------------------------------------- | --------------------------------------------- |
| [SPEC.md](SPEC.md)                              | Product specification and functional requirements |
| [ARCHITECTURE.md](ARCHITECTURE.md)              | System design, services, data flow, schema    |
| [AGENT_DESIGN.md](AGENT_DESIGN.md)              | Agent pipeline, contracts, prompts, audit     |
| [TECH_STACK.md](TECH_STACK.md)                  | Full stack with rationale and dependencies    |
| [SECURITY_GUARDRAILS.md](SECURITY_GUARDRAILS.md)| Security design, identity, PII, compliance    |
| [ROADMAP.md](ROADMAP.md)                        | Milestones and release versioning             |

---

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for how to set up the dev environment, branch conventions, and the PR process.

---

## License

Apache License 2.0 — see [LICENSE](LICENSE).
