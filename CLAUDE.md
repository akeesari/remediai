# RemediAI — Claude Code Instructions

## Read Before Writing Code

Always read these files first to understand current state:
`README.md` · `SPEC.md` · `ARCHITECTURE.md` · `AGENT_DESIGN.md` · `TECH_STACK.md` · `SECURITY_GUARDRAILS.md` · `ROADMAP.md`

Phase specs live in `docs/specs/phase-NN-*.md` — read the spec before implementing any phase.

---

## Spec-First Workflow — No Exceptions

**STOP before writing any code.** Follow this sequence every time, without skipping steps:

1. **Identify** the existing spec file in `docs/specs/` that covers the feature or change being requested. Every task maps to an existing phase — find it.
2. **Update that spec** (or create a new one if no existing phase covers it) to reflect what will be built: add new deliverables, update acceptance criteria, note any new dependencies or out-of-scope items.
3. **Update all affected documentation** in the same response: `SPEC.md`, `AGENT_DESIGN.md`, `ARCHITECTURE.md`, `ROADMAP.md`, and any relevant prompt files under `docs/prompts/`.
4. **Then implement.** Spec + docs update and implementation all ship in the same response.

Rules:
- Never create a new spec file for a task that fits an existing phase.
- Never implement before the relevant spec is updated.
- Never implement before affected documentation is updated.
- If a task genuinely spans multiple phases, update all affected specs.
- The spec update is not a summary of what you did — it is written *as if it always belonged there*, in spec voice (imperative, present tense, no past-tense narration).
- If the user asks for code changes without mentioning a spec, **stop and ask**: "Which spec covers this? Should I update an existing one or create a new phase?" Do not proceed until the spec question is resolved.

### Documentation sync checklist (run before every implementation)

For any code change, confirm these are updated in the same response:

| Changed area | Docs to update |
|---|---|
| New agent or agent behaviour | `AGENT_DESIGN.md` · relevant `phase-NN-*.md` |
| New API endpoint | `SPEC.md` (FR section) · `phase-NN-*.md` |
| New domain model field | `SPEC.md` (data model) · `AGENT_DESIGN.md` |
| Language-specific logic | `phase-06-triage-agent.md` · `phase-07-root-cause-agent.md` · affected prompts |
| New integration (SCM, ticketing, ingestion) | `TECH_STACK.md` · `ARCHITECTURE.md` · `SPEC.md` (integration points) |
| New phase | `ROADMAP.md` milestone entry |
| Prompt change | `docs/prompts/` version bump + spec reference updated |

---

## Commit Rules — No Exceptions

1. **Never** run `git add`, `git commit`, or `git push` without explicit user approval.
   Accepted signals: "commit", "yes", "go ahead", "approve". Silence is not approval.
2. After completing a phase: run `ruff` + `mypy --strict` + `pytest`.
3. For every project code change, validate a local Docker build before phase sign-off:
  - `cp .env.example .env` (if `.env` is missing)
  - `docker compose --env-file .env config`
  - `docker compose --env-file .env build`
4. Show a **Phase Summary**, then **stop and wait**.
5. One commit per phase. No squashing phases without permission.

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

---

## Language-Agnostic Development Rules

RemediAI supports multiple languages. Every code change must be evaluated against this checklist:

**Before implementing anything that touches exception handling, stack traces, triage rules, or file extensions:**

1. **Is this change language-specific?** If yes — stop. Check whether it belongs in a language module (e.g., `_RULES_BY_LANGUAGE["dotnet"]`) rather than the shared pipeline.
2. **Does this hardcode a file extension** (`.cs`, `.py`, `.js`, `.java`)? If yes — make it configurable or language-dispatched.
3. **Does this hardcode framework internal prefixes** (`System.`, `Microsoft.`, `site-packages/`)? If yes — add it to `language_internals.py` under the correct language key, not inline.
4. **Does this assume a stack trace format**? If yes — check that the parser handles all supported formats or explicitly documents which format it handles.

**Language support tiers (do not skip steps):**

| Tier | Languages | Status |
|------|-----------|--------|
| MVP | .NET | ✅ Complete |
| Foundation | Language-agnostic engine | Phase 36 |
| v1.x | Python | Phase 27 |
| v1.x | Node.js | Phase 28 |
| Future | Java | Unscheduled |

Adding Python or Node.js support without Phase 36 complete will create merge conflicts and regressions. **Do not implement Phase 27 or 28 until Phase 36 is committed.**

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

- Write specs **1–2 phases ahead**, not all at once. Specs written too early will be wrong.
- A spec must answer: Goal · Deliverables · Security touchpoints · Acceptance criteria · Out of scope. Nothing else is required.
- **Security touchpoints** — every spec author must answer these before writing implementation details:
  - Does this phase make an LLM call? → `scrub()` is required on all user-text fields.
  - Does this phase write agent decisions? → `AgentTraceEntry` in `state["agent_trace"]` is required.
  - Does this phase introduce a new credential? → Note it must come from `pydantic-settings`; Key Vault in production.
  - Does this phase expose a new HTTP endpoint? → State the authentication requirement, even if deferred.
  - Does this phase add or change language-specific logic? → Note the language scope and which other language tiers are affected.
- Cross-cutting concerns (PII scrubbing, structlog, audit log) are **foundations**, not hardening. They belong in the earliest phase that introduces the pattern — not in a later cleanup phase.
- When a phase modifies an existing agent's `_call_llm()`, explicitly confirm the existing `scrub()` calls are preserved.
- When a phase adds language-specific logic, explicitly confirm it is isolated to a language module and does not affect other languages.

---

## What's Next

After every task, end with a **"What's Next"** block: 2–3 options, exactly one marked `✅ Recommended`, tied to `ROADMAP.md` progress. Never ask the user what to do — present options and let them choose.

## Documentation Sync

Any code change must update relevant docs in the **same response**. Full doc-sync table is in `CONTRIBUTING.md`.
