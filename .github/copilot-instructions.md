# RemediAI — Copilot Instructions

## Read Before Writing Code

Always read these files first to understand current state:
`README.md` · `SPEC.md` · `ARCHITECTURE.md` · `AGENT_DESIGN.md` · `TECH_STACK.md` · `SECURITY_GUARDRAILS.md` · `ROADMAP.md`

---

## Commit Rules — No Exceptions

1. **Never** run `git add`, `git commit`, or `git push` without explicit user approval.
   Accepted signals: "commit", "yes", "go ahead", "approve". Silence is not approval.
2. After completing a phase: run `ruff` + `mypy --strict` + `pytest`, show a **Phase Summary**, then **stop and wait**.
3. One commit per phase. No squashing phases without permission.

**Required Phase Summary format:**

```
## Phase N Complete — Awaiting Your Approval
- ruff: ✅  mypy: ✅  tests: ✅ N passed
- [new]      path/to/file.py — what it does
- [modified] path/to/file.py — what changed
Reply "commit" to proceed, or give feedback to adjust first.
```

---

## MVP Build Order

1. Project structure + domain models  
2. PostgreSQL schema + Alembic migrations  
3. Azure Monitor KQL connector  
4. Ingestion service + Service Bus publisher  
5. Triage agent  
6. Root cause agent  
7. Code context agent  
8. RAG retrieval agent  
9. Fix planner agent  
10. Azure DevOps Bug integration  
11. FastAPI dashboard endpoints  
12. React dashboard  

Phase specs live in `docs/specs/phase-NN-*.md` — read the spec before implementing any phase.

---

## Safety Rules

- No secrets in code — use `pydantic-settings` + environment variables.
- Mask PII (emails, IPs, user IDs) before any LLM call.
- All agent decisions must be written to the `audit_log` table.
- No unauthenticated HTTP calls or shell execution inside agent tools.
- Never auto-merge PRs or modify production directly.
- **Any new agent that calls an LLM must call `scrub()` from `packages.integrations.pii_scrubber` on `exception_message` and `stack_trace` before `json.dumps`. Any phase that modifies an existing agent's `_call_llm()` must preserve these calls. See `docs/specs/phase-15-pii-scrubbing.md`.**

---

## Coding Standards

- Type hints on all function signatures.
- Pydantic v2 models for all data structures.
- SQLAlchemy 2.0 async ORM — no raw SQL except migrations.
- `ruff` (lint + format) and `mypy --strict` must pass before finishing any phase.
- `structlog` with `correlation_id` and `incident_id` bound to every log record.
- Unit tests for business logic; integration tests with mock clients for Azure connectors.

---

## Spec-Driven Development Rules

- Write specs **1–2 phases ahead**, not all at once.
- Every spec must answer these security touchpoints before listing deliverables:
  - New LLM call? → `scrub()` required.
  - Agent decision written? → `AgentTraceEntry` required.
  - New credential introduced? → `pydantic-settings` + Key Vault note required.
  - New HTTP endpoint? → authentication requirement stated.
- Cross-cutting concerns (PII, audit log, structlog) belong in the **earliest phase** that introduces the pattern — not in a later hardening phase.

---

## What's Next

After every task, end with a **"What's Next"** block: 2–3 options, exactly one marked `✅ Recommended`, tied to `ROADMAP.md` progress. Never ask the user what to do — present options and let them choose.

## Documentation Sync

Any code change must update relevant docs in the **same response**. Full doc-sync table is in `CONTRIBUTING.md`.
