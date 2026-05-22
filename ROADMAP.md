# RemediAI — Roadmap

## Current Status

Pre-development. Documentation phase in progress.

---

## Milestones

### Milestone 1 — Foundation (Target: Phase 1–2)

**Goal:** Working skeleton that proves the end-to-end flow.

- [x] Repository structure scaffolded
- [x] Domain models defined (Pydantic)
- [x] PostgreSQL schema created and migrated (Alembic)
- [x] Local dev environment with Docker Compose (Postgres, Redis)
- [ ] CI pipeline configured (Azure DevOps Pipelines)
- [x] Basic FastAPI app with health check endpoint
- [ ] Basic React dashboard shell

---

### Milestone 2 — Log Ingestion (Target: Phase 3)

**Goal:** Exceptions from Application Insights land in PostgreSQL as incidents.

- [ ] Azure Monitor KQL connector implemented
- [ ] Exception fingerprinting logic
- [ ] Deduplication against existing incidents
- [ ] Service Bus publisher
- [ ] Incident ingestion service running on schedule
- [ ] Integration test with mock Application Insights client

---

### Milestone 3 — Triage + Root Cause (Target: Phase 4–5)

**Goal:** Incidents are analyzed and root cause summaries are produced.

- [ ] LangGraph pipeline scaffolded
- [ ] Triage Agent: priority assignment, grouping, labeling
- [ ] Root Cause Agent: structured root cause summary with agent trace
- [ ] Code Context Agent: Azure DevOps Repos code lookup
- [ ] RAG Retrieval Agent: Azure AI Search query + result ranking
- [ ] Fix Planner Agent: remediation recommendations
- [ ] Full agent pipeline runs end-to-end on a sample incident
- [ ] Audit log entries written for every agent step

---

### Milestone 4 — Azure DevOps Bug Creation (Target: Phase 6)

**Goal:** Analyzed incidents automatically become Azure DevOps Bugs.

- [ ] Azure DevOps Boards REST client
- [ ] Bug creation from incident analysis
- [ ] Work item linked back to incident record
- [ ] Error handling and retry logic for ADO API failures
- [ ] Integration test with mock ADO client

---

### Milestone 5 — Dashboard (Target: Phase 7)

**Goal:** Engineers can see and manage incidents in the React UI.

- [ ] FastAPI endpoints: incident list, incident detail, metrics
- [ ] Pagination, filtering by status / priority / date
- [ ] React dashboard: incident list view
- [ ] React dashboard: incident detail view with root cause and recommendations
- [ ] React dashboard: metrics panel (volume, by status, top errors)
- [ ] Work item link visible on incident detail
- [ ] End-to-end acceptance test of first milestone flow

---

### Milestone 6 — Code Context + RAG Hardening (Target: Phase 7 continued)

**Goal:** Analysis quality improvements.

- [ ] Azure AI Search index populated with repo code and runbooks
- [ ] RAG results improve fix recommendation quality
- [ ] Code snippet context improves root cause precision
- [ ] Prompt versioning system in place
- [ ] Agent eval harness with sample incident fixtures

---

### Milestone 7 — PR Draft Generation (Target: Phase 8)

**Goal:** Approved recommendations can become pull requests.

- [ ] PR Agent: branch creation from fix recommendation
- [ ] PR Agent: code patch application
- [ ] PR Agent: draft PR creation in Azure DevOps
- [ ] Human approval gate before PR is created
- [ ] PR URL and status tracked in incident record
- [ ] Validation Agent: basic PR diff review

---

### Milestone 8 — Production Hardening (Target: Phase 10)

**Goal:** Platform is production-ready.

- [ ] AKS deployment with Helm charts
- [ ] Key Vault + Workload Identity integration
- [ ] KEDA autoscaling for ingestion and agent worker
- [ ] Structured logging and OpenTelemetry tracing
- [ ] Azure Monitor alerts for pipeline failures
- [ ] PII scrubbing before LLM transmission
- [ ] Load and soak testing
- [ ] Security review and penetration test
- [ ] Runbook for on-call operations

---

### Milestone 9 — Extended Language Support (Target: Phase 11+)

**Goal:** Expand beyond .NET.

- [ ] Node.js exception support
- [ ] Python application exception support
- [ ] Grafana / Loki log source connector
- [ ] Jira work item integration

---

## Release Versioning

| Version | Description                                           |
| ------- | ----------------------------------------------------- |
| v0.1    | Milestones 1–2: ingestion skeleton                    |
| v0.2    | Milestone 3: triage and root cause analysis           |
| v0.3    | Milestones 4–5: Bug creation and dashboard            |
| v0.4    | Milestone 6: RAG and code context hardening           |
| v0.5    | Milestone 7: PR draft generation                      |
| v1.0    | Milestone 8: production-ready release                 |
| v1.x    | Milestone 9: extended language and source support     |
