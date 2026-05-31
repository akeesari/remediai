---
sidebar_position: 3
title: Phase Workflow
---

# Phase Workflow

RemediAI is built using a **spec-driven, phase-based development process**. Each capability increment is a numbered phase with a written spec, a single commit, and a formal phase summary before merge.

---

## What is a phase?

A phase is a unit of work that:
- Has a single, well-defined goal
- Is described in a spec file (`docs/specs/phase-NN-*.md`) **before** implementation starts
- Produces one commit to `main`
- Passes `ruff`, `mypy --strict`, and `pytest` before committing

There are no phases without specs, and no implementation before the spec is reviewed.

---

## Spec format

Every phase spec must answer these five sections. Nothing else is required:

```markdown
# Phase N — Title

## Goal
One paragraph. What this phase delivers and why.

## Deliverables
Bulleted list of files, tables, endpoints, or agents that will exist after this phase.

## Security touchpoints
Answer each:
- Does this phase make an LLM call? → scrub() is required.
- Does this phase write agent decisions? → AgentTraceEntry is required.
- Does this phase introduce a new credential? → Must come from pydantic-settings / Key Vault.
- Does this phase expose a new HTTP endpoint? → State the authentication requirement.

## Acceptance criteria
Numbered list. Each criterion must be verifiable.

## Out of scope
What this phase explicitly does NOT deliver.
```

Spec files live in `docs/specs/phase-NN-<slug>.md`.

---

## Spec-first rule

Write specs **1–2 phases ahead**, not all at once. Specs written too early will be wrong because requirements change as you learn from implementation.

---

## Phase summary format

After completing a phase, before committing:

```
## Phase N Complete — Awaiting Your Approval
- ruff: ✅  mypy: ✅  tests: ✅ N passed
- [new]      path/to/file.py — what it does
- [modified] path/to/file.py — what changed
Reply "commit" to proceed, or give feedback to adjust first.
```

---

## Cross-cutting concerns are foundations

The following concerns are **always** enforced from the first phase that introduces them. They are not deferred to a later "hardening" phase:

| Concern | Rule |
|---------|------|
| PII scrubbing | Any agent that calls an LLM must call `scrub()` on `exception_message` and `stack_trace` |
| Audit log | Any agent decision must write an `AgentTraceEntry` to `state["agent_trace"]` |
| Structlog | All log lines must bind `correlation_id`, `incident_id`, `agent_name` |
| Secrets | All new credentials must come from `pydantic-settings` + environment variables |

---

## Current phase status

| Phase | Title | Status |
|-------|-------|--------|
| 1–21 | Foundation through PR Agent | ✅ Complete |
| 22 | Structured Logging + OpenTelemetry | In progress |
| 23 | Terraform + AKS + Helm | In progress |
| 24 | Key Vault + Workload Identity + KEDA | Pending |
| 25 | Azure Monitor Alerts + Runbook | Pending |
| 26 | Load + Security Testing | Pending |
| 27–29 | Python/Node.js support, Jira | Post-v1.0 |
| 30 | Documentation site (this site) | ✅ Complete |

See the [project roadmap on GitHub](https://github.com/akeesari/remediai/blob/main/ROADMAP.md) for the full dependency graph.

---

## Contributing a new phase

1. Check the [project roadmap on GitHub](https://github.com/akeesari/remediai/blob/main/ROADMAP.md) for the next unstarted phase.
2. Write the spec in `docs/specs/phase-NN-<slug>.md`.
3. Open a PR with just the spec — get it reviewed before writing code.
4. Implement the phase once the spec is approved.
5. Run `ruff`, `mypy --strict`, `pytest`.
6. Submit the implementation PR with the phase summary in the description.
