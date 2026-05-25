---
sidebar_position: 1
title: Prerequisites
---

# Prerequisites

Before setting up RemediAI you need the following accounts, tools, and Azure resources.

---

## Required tools

| Tool | Minimum version | Notes |
|------|----------------|-------|
| Python | 3.12+ | `python --version` to check |
| Node.js | 20 LTS | For the React dashboard |
| Docker Desktop | Latest stable | For local dependencies |
| Azure CLI (`az`) | 2.60+ | `az version` to check |
| Git | 2.40+ | |
| Poetry | 1.8+ | `pip install poetry` |

---

## Azure resources

You need a **non-production** Azure subscription with the following resources provisioned (or the ability to create them):

| Resource | Purpose |
|----------|---------|
| Azure Application Insights | Log source — where your .NET app writes exceptions |
| Azure Monitor Workspace | KQL query target |
| Azure OpenAI | GPT-4o model deployment for agent reasoning |
| Azure AI Search (Basic tier or above) | RAG index for runbooks, docs, and prior fixes |
| Azure DevOps organisation | Repos for code context; Boards for Bug creation |
| Azure Key Vault | Secret storage for all credentials |
| PostgreSQL and Redis storage for AKS | Persistent backing storage for the in-cluster database and cache |

:::tip Local development
For local development, PostgreSQL and Redis run in Docker. In AKS, both run inside the cluster as stateful workloads. You still need real Azure credentials for Application Insights, OpenAI, AI Search, DevOps, and Key Vault — use a dedicated **non-production** subscription.
:::

---

## Azure permissions

The identity you use to set up RemediAI must be able to:

- Create and assign Managed Identities
- Create role assignments on Application Insights, Service Bus, OpenAI, AI Search, Storage, and Key Vault
- Create Personal Access Tokens in Azure DevOps (or manage service connections)

---

## Azure DevOps setup

1. Create or identify an Azure DevOps organisation and project.
2. Create a **Personal Access Token (PAT)** with the following scopes:
   - `Work Items: Read & Write` (for Bug creation)
   - `Code: Read` (for code context)
   - `Code: Read & Write` (for PR Agent — Phase 2 only)
3. Store the PAT in Azure Key Vault (never in environment files committed to source control).

---

## .NET application requirements

RemediAI reads exceptions from Azure Monitor. Your .NET application must:

- Send telemetry to Application Insights (via the Application Insights SDK or OpenTelemetry with Azure Monitor exporter).
- Log unhandled exceptions with a full stack trace.
- Use the `exceptions` table in Application Insights (standard SDK behaviour).

---

## Next step

Once all prerequisites are met, proceed to [Installation](./installation).
