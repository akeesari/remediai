# RemediAI — Roadmap

## Current Status

**Active development.** Phases 1–21 are complete and committed. The end-to-end
flow now includes approval-gated draft PR creation and validation
(ingestion → triage → root cause → code context → RAG → fix planner → bug
creation → approval gate → PR agent → validation agent). Work remaining is
organised below into milestones and parallel development tracks.

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
- [ ] Full-stack local Docker Compose (all services) → **Phase 20**
- [x] CI pipelines configured (Azure DevOps Pipelines + GitHub Actions) → **Phase 21**

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
- [x] End-to-end acceptance test of first milestone flow → Phase 16 ✅

---

### Milestone 6 — Security + Quality Hardening (Phases 15–17)

**Goal:** Production-ready analysis quality and security baseline.

- [x] PII scrubbing before LLM transmission → Phase 15 ✅
- [x] Azure AI Search index populated with runbooks, source code, prior fixes → **Phase 17**
- [x] RAG results demonstrably improve fix recommendation quality → **Phase 17**
- [x] Code snippet context improves root cause precision → **Phase 17**
- [x] Prompt versioning system in place
- [x] Agent eval harness with sample incident fixtures

---

### Milestone 7 — PR Draft Generation (Phases 18–19)

**Goal:** Approved recommendations can become pull requests — with humans in the loop.

- [x] Human approval gate: dashboard action + approval API endpoint → **Phase 19**
- [x] PR Agent: branch creation from fix recommendation → **Phase 19**
- [x] PR Agent: code patch generation and application → **Phase 19**
- [x] PR Agent: draft PR creation in Azure DevOps → **Phase 19**
- [x] Validation Agent: PR diff review and safety check → **Phase 18**
- [x] PR URL and status tracked in incident record → **Phase 19**

---

### Milestone 8 — Production Hardening (Phases 20–26)

**Goal:** Platform is production-ready on AKS.

- [x] Full-stack local Docker Compose (all services) → **Phase 20**
- [x] CI pipelines: Azure DevOps Pipelines + GitHub Actions → **Phase 21**
- [ ] Structured logging + OpenTelemetry distributed tracing → **Phase 22**
- [ ] Azure infrastructure provisioned via Terraform + AKS + Helm, including in-cluster PostgreSQL and Redis → **Phase 23**
- [ ] Key Vault + Workload Identity + KEDA autoscaling (PostgreSQL scaler wired in Helm; infra module rollout pending) → **Phase 24**
- [ ] Azure Monitor alerts for pipeline failures + on-call runbook → **Phase 25**
- [ ] Load and soak testing → **Phase 26**
- [ ] Security review and penetration test → **Phase 26**

---

### Milestone 9 — Extended Language Support (Phases 27–29)

**Goal:** Expand beyond .NET. These are post-v1.0 and out of MVP scope.

- [ ] Python application exception support → **Phase 27**
- [ ] Grafana / Loki log source connector → **Phase 27**
- [ ] Node.js exception support → **Phase 28**
- [ ] Jira work item integration → **Phase 29**

---

### Milestone 10 — Platform Portability + Fleet Targeting (Phases 32–33)

**Goal:** Keep Azure/Foundry as the default profile while supporting
cloud-agnostic deployments and explicit target selection across Docker and
Kubernetes.

- [x] Provider abstraction layer + deployment profiles (`azure-foundry`, `portable`) → **Phase 32**
- [ ] Target registry + runtime discovery/selection for Docker and Kubernetes → **Phase 33**

---

## Parallel Development Tracks

Remaining work in Phases 20–26 is split into three independent tracks that can
be staffed in parallel. Phase 26 (Load + Security Testing) is the final merge
gate and runs only after all three tracks are complete.

```
Track A — DevOps & Infrastructure    Track B — Observability
──────────────────────────────────   ─────────────────────────────────
Phase 20: Local Docker Compose           Phase 22: Structured Logging
    ↓                                        + OpenTelemetry
Phase 21: CI Pipeline
    ↓
Phase 23: Terraform + AKS + Helm
    ↓
Phase 24: Key Vault + KEDA
    ↓
Phase 25: Azure Monitor Alerts


Track C — Validation Gate
──────────────────────────────────
Phase 26: Load + Security Testing
```

**All tracks merge at Phase 26 (Load + Security Testing).**

Starting points (with Phases 1–19 complete):
- Track A: start Phase 20
- Track B: start Phase 22
- Track C: start Phase 26 after Tracks A and B

---

## Remaining Phases — Spec Required Before Implementation

A spec (`docs/specs/phase-NN-*.md`) must exist and be reviewed before any
code is written for that phase.

### Track A — DevOps & Infrastructure

| Phase | Title | Depends on | Spec |
|---|---|---|---|
| 20 | Local Full-Stack Docker Compose | Phase 16 | `docs/specs/phase-20-local-docker-compose.md` |
| 21 | CI Pipelines (Azure DevOps + GitHub Actions) | Phase 20 | `docs/specs/phase-21-ci-pipeline.md` |
| 23 | Terraform IaC + AKS Deployment + Helm | Phase 21 | `docs/specs/phase-23-terraform-aks-helm.md` |
| 24 | Key Vault + Workload Identity + KEDA | Phase 23 | `docs/specs/phase-24-keyvault-keda.md` |
| 25 | Azure Monitor Alerts + Runbook | Phase 24 | `docs/specs/phase-25-alerting-runbook.md` |

### Track B — Observability

| Phase | Title | Depends on | Spec |
|---|---|---|---|
| 22 | Structured Logging + OpenTelemetry Tracing | Phase 21 | `docs/specs/phase-22-observability.md` |
| 26 | Load Testing + Security Review | All tracks complete | `docs/specs/phase-26-load-security-testing.md` |

### Post-v1.0 Extensions (out of MVP scope)

| Phase | Title | Spec |
|---|---|---|
| 27 | Python Exception Support + Grafana/Loki Connector | `docs/specs/phase-27-python-loki.md` |
| 28 | Node.js Exception Support | `docs/specs/phase-28-nodejs-support.md` |
| 29 | Jira Work Item Integration | `docs/specs/phase-29-jira-integration.md` |

### Platform Portability + Fleet Targeting

| Phase | Title | Spec |
|---|---|---|
| 32 | Provider Abstraction + Deployment Profiles | `docs/specs/phase-32-provider-abstraction-profiles.md` |
| 33 | Target Registry + Discovery/Selection | `docs/specs/phase-33-target-registry-discovery-selection.md` |

---

## Is This a Complete Product?

At the end of Phase 26, RemediAI is production-ready on the Azure reference
stack. Phases 27–33 extend language support, portability, and fleet target
management for broader distribution scenarios.

| Capability | Covered by |
|---|---|
| Exception ingestion from App Insights | Phase 3 ✅ |
| AI triage + root cause + fix recommendations | Phases 6–10 ✅ |
| Azure DevOps Bug creation | Phase 11 ✅ |
| React dashboard | Phase 14 ✅ |
| PII scrubbing + data security | Phase 15 ✅ |
| E2E test coverage | Phase 16 ✅ |
| RAG quality + populated search index | Phase 17 ✅ |
| Draft PR with human approval | Phases 18–19 ✅ |
| Full local dev stack (browser-testable) | Phase 20 |
| CI/CD pipeline | Phase 21 ✅ |
| Structured logging + tracing | Phase 22 |
| Azure infrastructure (IaC + AKS + Helm) | Phase 23 |
| Key Vault + Workload Identity + KEDA | Phase 24 |
| Observability + alerting | Phase 25 |
| Load + security validation | Phase 26 |
| Provider abstraction + install profiles | Phase 32 |
| Docker/Kubernetes target registry | Phase 33 |

---

## Completed Phases

| Phase | Title | Commit |
|---|---|---|
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
| 32 | Provider Abstraction + Deployment Profiles | `677d3af` |

---

## Release Versioning

| Version | Milestones | Description |
|---|---|---|
| v0.1 | 1–2 | Ingestion skeleton |
| v0.2 | 3 | Triage and root cause analysis |
| v0.3 | 4–5 | Bug creation and dashboard |
| v0.4 | 6–7 | Security hardening, RAG quality, draft PR |
| v1.0 | 8 | Production-ready on AKS |
| v1.x | 9 | Extended language and source support |
