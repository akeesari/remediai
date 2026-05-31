# RemediAI — Product Specification

## Overview

RemediAI is an AI-powered exception analysis and remediation platform for enterprise applications across languages and runtimes. It ingests application exceptions from observability platforms (Azure Monitor / Application Insights for MVP; OpenTelemetry, Loki, and webhooks in later phases), runs an agentic analysis pipeline, creates work items, and generates pull requests for human review.

**Language support:** .NET is the MVP target. Python support is added in Phase 27. Node.js in Phase 28. Java in a future phase. The pipeline, domain model, and agent contracts are language-agnostic by design — language-specific behaviour (stack trace parsing, triage rules, framework prefix filtering) is isolated to pluggable modules.

## Problem Statement

Engineering teams lose significant time triaging the same recurring exception patterns, tracing root causes across distributed services, and manually creating work items. RemediAI automates the investigation and triage steps so engineers can focus on fixing rather than finding.

## Goals

- Reduce mean time to triage (MTTT) for application exceptions.
- Produce structured root cause summaries with supporting evidence.
- Automatically create Azure DevOps Bugs with full context attached.
- Provide a dashboard for tracking incident and remediation status.
- Keep humans in the loop for all code changes.

## Non-Goals (MVP)

- Auto-merging pull requests.
- Direct modification of production systems.
- Jira or GitHub Issues integration (Phase 29).
- Python, Node.js, or Java application support (Phases 27–28; Java future).
- Grafana / Loki / Datadog ingestion (Phase 27+).
- GitHub source control (Phase 38).
- Self-healing without human approval.

> **Clarification:** "not in MVP" means the ingestion connector, stack trace parser,
> and triage rules for that language are not yet implemented — **not** that the
> platform is architecturally tied to .NET. All agent logic, domain models, and APIs
> are language-agnostic.

---

## User Roles

| Role              | Description                                                          |
| ----------------- | -------------------------------------------------------------------- |
| Platform Engineer | Configures RemediAI, connects Azure resources, manages integrations. |
| Developer         | Reviews incidents, approves remediation recommendations, merges PRs. |
| Engineering Lead  | Monitors dashboard metrics, sets triage policies and SLAs.           |
| Auditor           | Reviews agent decision logs and audit trails.                        |

---

## Functional Requirements

### FR-1 — Log Ingestion

- Connect to Azure Monitor / Application Insights via KQL queries.
- Poll for new exceptions on a configurable interval.
- Deduplicate exceptions by fingerprint (exception type + stack trace hash).
- Publish new incidents to Azure Service Bus.

### FR-2 — Incident Management

- Store incidents in PostgreSQL with status lifecycle: `new → triaging → analyzed → bug_created → resolved`.
- Attach raw exception payload, stack trace, and metadata to each incident.
- Support manual incident creation via API for testing.

### FR-3 — Triage Agent

- Group related exceptions into a single incident where appropriate.
- Assign priority based on exception frequency, affected service, and error type.
- Detect known patterns (null reference, timeout, authentication failures) and apply standard triage labels across all supported languages.

### FR-4 — Root Cause Agent

- Analyze exception type, message, stack trace, and surrounding log context.
- Identify the likely faulty component, method, or service.
- Produce a structured root cause summary (JSON + human-readable text).
- Store reasoning steps for auditability.

### FR-5 — Code Context Agent

- Query Azure DevOps Repos to locate source files referenced in the stack trace.
- Extract relevant code snippets for the top N stack frames.
- Attach snippets to the incident analysis record.

### FR-6 — RAG Retrieval Agent

- Search Azure AI Search index over source code, documentation, runbooks, and prior remediation records.
- Return the top K most relevant results with relevance scores.
- Include retrieved context in the Fix Planner prompt.

### FR-7 — Fix Planner Agent

- Generate a ranked list of remediation recommendations based on root cause and retrieved context.
- Each recommendation includes: description, affected file(s), suggested change, confidence score.
- Recommendations are stored and linked to the incident.

### FR-8 — Azure DevOps Bug Creation

- Create an Azure DevOps Bug work item in the configured project.
- Populate title, description, repro steps, and system info from the incident analysis.
- Link the incident ID back to the work item.
- Record the created work item ID in the incident record.

### FR-9 — Dashboard API

- Expose REST endpoints for incident list, incident detail, and remediation status.
- Support filtering by status, priority, date range, and service.
- Return summary metrics: total incidents, by status, by priority, MTTT.

### FR-10 — React Dashboard

- Display incident list with status badges and priority indicators.
- Show incident detail: exception, root cause summary, recommendations, work item link.
- Show metrics panel with incident volume, resolution rate, and top error types.

### FR-11 — PR Agent (Phase 2)

- Generate a branch and draft pull request in Azure DevOps Repos.
- Apply the approved Fix Planner recommendation as a code patch.
- Flag the PR for human review — never auto-merge.
- Record PR URL and status in the incident record.

---

## Non-Functional Requirements

| Category       | Requirement                                                                 |
| -------------- | --------------------------------------------------------------------------- |
| Availability   | 99.5% uptime for ingestion and API services.                                |
| Latency        | Incident analysis complete within 3 minutes of exception ingestion.         |
| Throughput     | Handle up to 500 incidents per hour in MVP configuration.                   |
| Security       | All secrets via Key Vault. No secrets in code or config files.              |
| Observability  | Structured JSON logging, correlation IDs, distributed tracing.              |
| Auditability   | Every agent action stored in an immutable audit table.                      |
| Data Residency | All data processed and stored within the Azure region of the tenant.        |
| PII Handling   | Exception payloads scrubbed of PII before transmission to LLM endpoints.    |

---

## Data Model (Summary)

### Incident

| Field             | Type      | Description                                 |
| ----------------- | --------- | ------------------------------------------- |
| id                | UUID      | Primary key                                 |
| correlation_id    | UUID      | Cross-service trace ID                      |
| source            | string    | Application name / resource                 |
| exception_type    | string    | Exception class name (language-native format) |
| exception_message | string    | Exception message text                      |
| stack_trace       | text      | Full stack trace                            |
| fingerprint       | string    | Deduplication hash                          |
| priority          | enum      | critical / high / medium / low              |
| status            | enum      | new / triaging / analyzed / bug_created / resolved |
| created_at        | timestamp |                                             |
| updated_at        | timestamp |                                             |

### IncidentAnalysis

| Field           | Type | Description                            |
| --------------- | ---- | -------------------------------------- |
| id              | UUID |                                        |
| incident_id     | UUID | FK to Incident                         |
| root_cause      | text | Human-readable root cause summary      |
| root_cause_json | JSON | Structured root cause breakdown        |
| recommendations | JSON | Ordered list of fix recommendations    |
| code_snippets   | JSON | Relevant source file extracts          |
| rag_results     | JSON | RAG retrieval hits                     |
| agent_trace     | JSON | Step-by-step reasoning audit           |
| created_at      | timestamp |                                   |

### WorkItem

| Field         | Type      | Description                      |
| ------------- | --------- | -------------------------------- |
| id            | UUID      |                                  |
| incident_id   | UUID      | FK to Incident                   |
| ado_item_id   | integer   | Azure DevOps work item ID        |
| ado_item_url  | string    | Direct link                      |
| item_type     | enum      | bug / task                       |
| created_at    | timestamp |                                  |

---

## Integration Points

| System                        | Protocol          | Auth Method          |
| ----------------------------- | ----------------- | -------------------- |
| Azure Monitor / App Insights  | REST / KQL        | Managed Identity     |
| Azure Service Bus             | AMQP              | Managed Identity     |
| Azure AI Foundry / OpenAI     | REST              | Managed Identity     |
| Azure AI Search               | REST              | Managed Identity     |
| Azure DevOps Repos            | REST              | PAT / Service Principal |
| Azure DevOps Boards           | REST              | PAT / Service Principal |
| Azure Key Vault               | REST              | Managed Identity     |
| Azure Blob Storage            | REST              | Managed Identity     |
| PostgreSQL                    | TCP/TLS           | Password via Key Vault |

---

## Acceptance Criteria — First Milestone

1. An application exception logged in Application Insights is detected within 5 minutes.
2. The exception is stored as an incident in PostgreSQL with `new` status.
3. The LangGraph pipeline transitions the incident to `analyzed` with a root cause summary.
4. An Azure DevOps Bug is created with incident context and linked to the incident record.
5. The incident and its Bug link appear on the React dashboard.
