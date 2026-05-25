---
id: roadmap
title: Roadmap
sidebar_label: Roadmap
---

# Roadmap

RemediAI follows a phase-based build plan. Phases 1–21 are complete. The remaining work runs across parallel tracks targeting v1.0 production readiness.

---

## Current status

**Active development — v0.4.** Phases 1–21 are complete and committed. The end-to-end flow includes:

- Exception ingestion → triage → root cause → code context → RAG → fix planner → bug creation
- Human approval gate → PR agent → validation agent
- React dashboard with incident list, detail view, and approval workflow
- Full PII scrubbing, audit log, and CI/CD pipeline

---

## Milestones

### Milestone 1 — Foundation ✅

Working skeleton with domain models, PostgreSQL schema, and FastAPI shell.

### Milestone 2 — Log Ingestion ✅

Azure Monitor KQL connector, fingerprinting, deduplication, Service Bus publisher.

### Milestone 3 — Triage + Root Cause ✅

Full LangGraph pipeline: Triage → Root Cause → Code Context → RAG → Fix Planner → Bug Creation.

### Milestone 4 — Azure DevOps Bug Creation ✅

ADO Boards REST client, Bug creation, work item linked to incident.

### Milestone 5 — Dashboard ✅

FastAPI endpoints, React incident list, detail view, metrics panel.

### Milestone 6 — Security + Quality Hardening ✅

PII scrubbing, RAG index population, prompt versioning, agent eval harness.

### Milestone 7 — PR Draft Generation ✅

Human approval gate, PR Agent, Validation Agent, draft PR workflow.

### Milestone 8 — Production Hardening (In progress)

| Phase | Title | Status |
|-------|-------|--------|
| 20 | Local Full-Stack Docker Compose | ✅ Complete |
| 21 | CI Pipelines (GitHub Actions + Azure DevOps) | ✅ Complete |
| 22 | Structured Logging + OpenTelemetry Tracing | In progress |
| 23 | Terraform IaC + AKS Deployment + Helm (including PostgreSQL + Redis on AKS) | Planned |
| 24 | Key Vault + Workload Identity + KEDA | Planned |
| 25 | Azure Monitor Alerts + Runbook | Planned |
| 26 | Load Testing + Security Review | Planned |

### Milestone 9 — Extended Language Support (Post-v1.0)

| Phase | Title |
|-------|-------|
| 27 | Python Exception Support + Grafana/Loki Connector |
| 28 | Node.js Exception Support |
| 29 | Jira Work Item Integration |

---

## Parallel development tracks

Phases 22–26 can be staffed in parallel:

```
Track A — DevOps & Infrastructure    Track B — Observability
──────────────────────────────────   ────────────────────────────
Phase 20: Local Docker Compose ✅    Phase 22: Structured Logging
Phase 21: CI Pipeline ✅                     + OpenTelemetry
Phase 23: Terraform + AKS + Helm
Phase 24: Key Vault + KEDA
Phase 25: Azure Monitor Alerts

Track C — Validation Gate
──────────────────────────────────
Phase 26: Load + Security Testing
         (requires Tracks A + B complete)
```

---

## Version plan

| Version | Milestones | Description |
|---------|-----------|-------------|
| v0.1 | 1–2 | Ingestion skeleton |
| v0.2 | 3 | Triage and root cause analysis |
| v0.3 | 4–5 | Bug creation and dashboard |
| v0.4 | 6–7 | Security hardening, RAG quality, draft PR |
| **v1.0** | **8** | **Production-ready on AKS** |
| v1.x | 9 | Extended language and source support |

---

## Completed phases

| Phase | Title | Commit |
|-------|-------|--------|
| 1 | Project Structure + FastAPI Shell | `c23ba2d` |
| 2 | Domain Models (Pydantic) | `92dd0da` |
| 3 | PostgreSQL Schema + Alembic Migrations | `3024937` |
| 4 | Azure Monitor KQL Connector | `9f1df8c` |
| 5 | Ingestion Service + Service Bus Publisher | `c44c592` |
| 6 | Triage Agent | `170bbb5` |
| 7 | Root Cause Agent | `07e7fcf` |
| 8 | Code Context Agent + ADO Repos Client | `8580bfb` |
| 9 | RAG Retrieval Agent + Azure AI Search Client | `d98c333` |
| 10 | Fix Planner Agent | `f38778b` |
| 11 | Azure DevOps Bug Integration | `ec92290` |
| 12 | FastAPI Dashboard Endpoints | `47539b5` |
| 13 | Prompt Versioning Registry + Agent Eval Harness | `cc59329` |
| 14 | React Dashboard | `1521a40` |
| 15 | PII Scrubbing | `fe4132d` |
| 16 | End-to-End Acceptance Tests | `d4ab7fc` |
| 17 | AI Search Index Population + RAG Quality Hardening | `3a2e33c` |
| 18 | Validation Agent — PR Diff Review | `63c0862` |
| 19 | PR Agent + Human Approval Gate | `63c0862` |
| 20 | Local Full-Stack Docker Compose | — |
| 21 | CI Pipelines (GitHub Actions + Azure DevOps) | — |
| 30 | Documentation Site (this site) | — |

---

## What "complete" looks like at v1.0

At the end of Phase 26, RemediAI will be:

- Fully deployed on AKS with Helm charts and in-cluster PostgreSQL and Redis
- Provisioned via Terraform
- Using Key Vault + Workload Identity — zero stored credentials
- Horizontally scalable via KEDA and HPA
- Observable via OpenTelemetry + Azure Monitor + Grafana
- Validated under load and security-reviewed

No additional phases will be added before v1.0 unless product requirements change.

---

## Contributing

Interested in helping ship v1.0? See [Phase Workflow](./contributing/phase-workflow) for how phases work and how to contribute one.
