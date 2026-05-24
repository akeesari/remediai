# Phase 28 — Load Testing + Security Review

## Goal

Validate that the platform meets its NFR throughput target (500 incidents/hour)
and that the production deployment has no exploitable vulnerabilities.  Both
activities must be completed before the v1.0 release tag is cut.

---

## Background

SPEC.md NFR: "Handle up to 500 incidents per hour in MVP configuration."
SECURITY_GUARDRAILS.md: "Security review and penetration test" required for
Milestone 8.

---

## Deliverables

| Artifact | Description |
|---|---|
| `tests/load/incident_ingest.js` | k6 load test: POST incidents at target rate, assert p95 latency |
| `tests/load/pipeline_throughput.js` | k6 load test: measure end-to-end pipeline completion rate |
| `tests/load/api_read.js` | k6 load test: incident list + detail reads under concurrent load |
| `tests/load/config.js` | Shared k6 config (base URL, thresholds, stages) |
| `docs/load-test-results/baseline.md` | Template for recording test run results |
| `docs/security/pentest-scope.md` | Penetration test scope, rules of engagement, excluded systems |
| `docs/security/security-review-checklist.md` | Pre-release security checklist |
| `Makefile` update | `load-test` target |

---

## Load Test Scenarios

### Scenario 1 — Ingestion Throughput (`incident_ingest.js`)

Simulates 500 incidents/hour arriving via the Service Bus ingestion path.

```
Stages:
  0–2 min:   ramp from 0 to 8.33 RPS (500/hr)
  2–10 min:  sustain 8.33 RPS
  10–12 min: ramp down to 0

Thresholds:
  http_req_duration p(95) < 500ms   (ingestion API acknowledgement)
  http_req_failed < 1%
  pipeline_completion_rate > 95%     (custom metric: incidents reaching "analyzed")
```

### Scenario 2 — API Read Concurrency (`api_read.js`)

Simulates 50 concurrent dashboard users paging through incidents.

```
Virtual Users: 50
Duration: 10 minutes

Thresholds:
  http_req_duration p(95) < 300ms   (GET /api/v1/incidents)
  http_req_duration p(95) < 500ms   (GET /api/v1/incidents/{id})
  http_req_failed < 0.1%
```

### Scenario 3 — Pipeline Soak Test (`pipeline_throughput.js`)

Runs at 60% target load (300 incidents/hour) for 60 minutes to detect memory
leaks and database connection exhaustion.

```
Duration: 60 minutes at 5 RPS
Thresholds:
  No memory growth > 20% over test duration (measured via kubectl top)
  Database connection pool waiting metric < 5 throughout
  Error rate < 0.5%
```

---

## k6 Config (`tests/load/config.js`)

```javascript
export const BASE_URL = __ENV.BASE_URL || 'http://localhost:8000'
export const THRESHOLDS = {
  http_req_duration: ['p(95)<500'],
  http_req_failed:   ['rate<0.01'],
}
```

---

## Makefile Addition

```makefile
load-test:
    k6 run tests/load/incident_ingest.js --env BASE_URL=$(API_URL)
```

---

## Security Review Checklist (`docs/security/security-review-checklist.md`)

Pre-release checklist covering:

### Code Review
- [ ] No secrets in source code (`detect-secrets` baseline clean).
- [ ] All API inputs validated via Pydantic (no raw `request.body` parsing).
- [ ] No raw SQL — SQLAlchemy ORM only.
- [ ] No shell execution inside agent tools.
- [ ] PII scrubber applied before all LLM calls (Phase 15).
- [ ] Audit log written for every agent action.
- [ ] PR Agent never sets auto-complete on PRs.

### Infrastructure
- [ ] All secrets in Key Vault (Phase 25).
- [ ] Network policies deny unexpected cross-service traffic (Phase 24).
- [ ] Private endpoints on all Azure PaaS services (Phase 25).
- [ ] WAF enabled on Application Gateway ingress.
- [ ] TLS 1.2+ enforced; TLS 1.0/1.1 disabled.
- [ ] Container images scanned by Microsoft Defender for Containers.
- [ ] Base images pinned by digest.

### Dependencies
- [ ] `pip-audit` finds no critical or high CVEs.
- [ ] `npm audit` finds no critical or high CVEs.
- [ ] All Python dependencies pinned in `poetry.lock`.
- [ ] All npm dependencies pinned in `package-lock.json`.

### Identity
- [ ] All service identities use Workload Identity (no service principal secrets).
- [ ] ADO PAT has minimum required scope.
- [ ] No wildcard RBAC role assignments.

---

## Penetration Test Scope (`docs/security/pentest-scope.md`)

### In Scope
- FastAPI backend API (public ingress endpoint).
- React dashboard (public ingress endpoint).
- Service Bus ingestion path (authenticated endpoint).
- Azure AD authentication flows (if implemented).

### Out of Scope
- AKS control plane.
- Azure platform services (Service Bus, Key Vault, PostgreSQL) — tested by Microsoft.
- Third-party SaaS integrations (Azure DevOps, Azure OpenAI).
- Production data — test must use a dedicated staging environment.

### Rules of Engagement
- Testing conducted against the staging environment only.
- No denial-of-service techniques.
- Findings reported to the security team within 24 hours of discovery.
- Critical findings block the v1.0 release until resolved.

---

## Acceptance Criteria

- All three k6 load test scenarios complete without threshold failures.
- Soak test shows no memory growth trend over 60 minutes.
- Security checklist is 100% complete with no unchecked items.
- Penetration test report received; no critical or high findings unresolved.
- Load test baseline results documented in `docs/load-test-results/baseline.md`.

---

## Out of Scope

- Performance optimisation beyond meeting the 500 incidents/hour NFR.
- Automated continuous penetration testing (future security operations phase).
- Browser-based UI load testing (k6 browser extension is a stretch goal).
