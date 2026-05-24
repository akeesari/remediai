# RemediAI — Roadmap

## Current Status

**Active development.** Phases 1–14 complete and committed. MVP core pipeline
(ingestion → triage → root cause → code context → RAG → fix planner → bug
creation) is fully operational with a React dashboard and versioned prompt
registry.  Work remaining is organised below into milestones and then as a
discrete **Pending Phases** backlog — each phase must have a spec in
`docs/specs/` before any implementation begins.

---

## Milestones

### Milestone 1 — Foundation (Phases 1–2)

**Goal:** Working skeleton that proves the end-to-end flow.

- [x] Repository structure scaffolded
- [x] Domain models defined (Pydantic)
- [x] PostgreSQL schema created and migrated (Alembic)
- [x] Local dev environment with Docker Compose (Postgres, Redis)
- [x] Basic FastAPI app with health check endpoint
- [x] React dashboard shell
- [ ] CI pipeline configured (Azure DevOps Pipelines) → **Phase 15**

---

### Milestone 2 — Log Ingestion (Phase 3)

**Goal:** Exceptions from Application Insights land in PostgreSQL as incidents.

- [x] Azure Monitor KQL connector implemented
- [x] Exception fingerprinting logic
- [x] Deduplication against existing incidents
- [x] Service Bus publisher
- [x] Incident ingestion service running on schedule
- [x] Integration test with mock Application Insights client

---

### Milestone 3 — Triage + Root Cause (Phases 4–9)

**Goal:** Incidents are analyzed and root cause summaries are produced.

- [x] LangGraph pipeline scaffolded
- [x] Triage Agent: priority assignment, grouping, labeling
- [x] Root Cause Agent: structured root cause summary with agent trace
- [x] Code Context Agent: Azure DevOps Repos code lookup
- [x] RAG Retrieval Agent: Azure AI Search query + result ranking
- [x] Fix Planner Agent: remediation recommendations
- [x] Full agent pipeline runs end-to-end on a sample incident
- [x] Audit log entries written for every agent step

---

### Milestone 4 — Azure DevOps Bug Creation (Phase 11)

**Goal:** Analyzed incidents automatically become Azure DevOps Bugs.

- [x] Azure DevOps Boards REST client
- [x] Bug creation from incident analysis
- [x] Work item linked back to incident record
- [x] Error handling and retry logic for ADO API failures
- [x] Integration test with mock ADO client

---

### Milestone 5 — Dashboard (Phases 12 + 14)

**Goal:** Engineers can see and manage incidents in the React UI.

- [x] FastAPI endpoints: incident list, incident detail, metrics
- [x] Pagination, filtering by status / priority / date
- [x] React dashboard: incident list view
- [x] React dashboard: incident detail view with root cause and recommendations
- [x] React dashboard: metrics panel (volume, by status, top errors)
- [x] Work item link visible on incident detail
- [ ] End-to-end acceptance test of first milestone flow → **Phase 16**

---

### Milestone 6 — Security + Quality Hardening (Phases 15–18)

**Goal:** Production-ready analysis quality and security baseline.

- [ ] PII scrubbing before LLM transmission → **Phase 15**
- [ ] Azure AI Search index populated with runbooks, source code, prior fixes → **Phase 17**
- [ ] RAG results demonstrably improve fix recommendation quality → **Phase 18**
- [ ] Code snippet context improves root cause precision → **Phase 18**
- [x] Prompt versioning system in place
- [x] Agent eval harness with sample incident fixtures

---

### Milestone 7 — PR Draft Generation (Phases 19–21)

**Goal:** Approved recommendations can become pull requests — with humans in the loop.

- [ ] PR Agent: branch creation from fix recommendation → **Phase 19**
- [ ] PR Agent: code patch generation and application → **Phase 19**
- [ ] PR Agent: draft PR creation in Azure DevOps → **Phase 19**
- [ ] Human approval gate: dashboard action + approval API endpoint → **Phase 20**
- [ ] Validation Agent: PR diff review and safety check → **Phase 21**
- [ ] PR URL and status tracked in incident record → **Phase 19**

---

### Milestone 8 — Production Hardening (Phases 22–27)

**Goal:** Platform is production-ready on AKS.

- [ ] CI pipeline: Azure DevOps Pipelines YAML → **Phase 22**
- [ ] Structured logging + OpenTelemetry distributed tracing → **Phase 23**
- [ ] AKS deployment with Helm charts → **Phase 24**
- [ ] Key Vault + Workload Identity integration → **Phase 25**
- [ ] KEDA autoscaling for ingestion and agent worker → **Phase 26**
- [ ] Azure Monitor alerts for pipeline failures + on-call runbook → **Phase 27**
- [ ] Load and soak testing → **Phase 28**
- [ ] Security review and penetration test → **Phase 28**

---

### Milestone 9 — Extended Language Support (Phases 29–32)

**Goal:** Expand beyond .NET.

- [ ] Node.js exception support → **Phase 29**
- [ ] Python application exception support → **Phase 30**
- [ ] Grafana / Loki log source connector → **Phase 31**
- [ ] Jira work item integration → **Phase 32**

---

## Pending Phases — Spec Required Before Implementation

Each row is a discrete unit of work. A spec (`docs/specs/phase-NN-*.md`) must
exist and be reviewed before any code is written for that phase.

| Phase | Title | Milestone | Spec |
|---|---|---|---|
| 15 | PII Scrubbing Middleware | 6 | `docs/specs/phase-15-pii-scrubbing.md` |
| 16 | End-to-End Acceptance Tests | 5 | `docs/specs/phase-16-e2e-acceptance-tests.md` |
| 17 | AI Search Index Population | 6 | `docs/specs/phase-17-search-index-population.md` |
| 18 | RAG & Code Context Quality Hardening | 6 | `docs/specs/phase-18-rag-quality-hardening.md` |
| 19 | PR Agent — Branch, Patch & Draft PR | 7 | `docs/specs/phase-19-pr-agent.md` |
| 20 | Human Approval Gate | 7 | `docs/specs/phase-20-human-approval-gate.md` |
| 21 | Validation Agent — PR Diff Review | 7 | `docs/specs/phase-21-validation-agent.md` |
| 22 | CI Pipeline — Azure DevOps Pipelines | 1 / 8 | `docs/specs/phase-22-ci-pipeline.md` |
| 23 | Structured Logging + OpenTelemetry Tracing | 8 | `docs/specs/phase-23-observability.md` |
| 24 | AKS Deployment + Helm Charts | 8 | `docs/specs/phase-24-aks-helm.md` |
| 25 | Key Vault + Workload Identity | 8 | `docs/specs/phase-25-keyvault-workload-identity.md` |
| 26 | KEDA Autoscaling | 8 | `docs/specs/phase-26-keda-autoscaling.md` |
| 27 | Azure Monitor Alerts + Runbook | 8 | `docs/specs/phase-27-alerting-runbook.md` |
| 28 | Load Testing + Security Review | 8 | `docs/specs/phase-28-load-security-testing.md` |
| 29 | Node.js Exception Support | 9 | `docs/specs/phase-29-nodejs-support.md` |
| 30 | Python Application Exception Support | 9 | `docs/specs/phase-30-python-support.md` |
| 31 | Grafana / Loki Log Source Connector | 9 | `docs/specs/phase-31-grafana-loki-connector.md` |
| 32 | Jira Work Item Integration | 9 | `docs/specs/phase-32-jira-integration.md` |

---

## Completed Phases

| Phase | Title | Commit |
|---|---|---|
| 1 | Project Structure + FastAPI Shell | `c23ba2d` |
| 2 | Domain Models (Pydantic) | `92dd0da` |
| 3 | PostgreSQL Schema + Alembic Migrations | `3024937` |
| 4 | Azure Monitor KQL Connector | — |
| 5 | Ingestion Service + Service Bus Publisher | — |
| 6 | Triage Agent | `170bbb5` |
| 7 | Root Cause Agent | `07e7fcf` |
| 8 | Code Context Agent + ADO Repos Client | `8580bfb` |
| 9 | RAG Retrieval Agent + Azure AI Search Client | `d98c333` |
| 10 | Fix Planner Agent | `f38778b` |
| 11 | Azure DevOps Bug Integration | `ec92290` |
| 12 | FastAPI Dashboard Endpoints | `47539b5` |
| 13 | Prompt Versioning Registry + Agent Eval Harness | `cc59329` |
| 14 | React Dashboard | `1521a40` |

---

## Release Versioning

| Version | Milestones | Description |
|---|---|---|
| v0.1 | 1–2 | Ingestion skeleton |
| v0.2 | 3 | Triage and root cause analysis |
| v0.3 | 4–5 | Bug creation and dashboard |
| v0.4 | 6 | Security hardening + RAG quality |
| v0.5 | 7 | PR draft generation |
| v1.0 | 8 | Production-ready on AKS |
| v1.x | 9 | Extended language and source support |
