---
applyTo: "apps/worker/agents/**/*.py,packages/agent_runtime/**/*.py,docs/prompts/**/*.md,tests/agent-evals/**/*.py"
---

# Agent Safety And Audit Rules

- Treat prompts as contracts: keep input assumptions and output schema explicit.
- Never allow agent tools to execute arbitrary shell commands.
- Never allow unauthenticated outbound HTTP requests.
- Redact or mask PII before any LLM call. Concretely: call `scrub()` from `packages.integrations.pii_scrubber` on `exception_message` and `stack_trace` before `json.dumps` in every agent's `_call_llm()`. If you are modifying an existing `_call_llm()`, verify the `scrub()` calls are still present after your change.
- Record every agent step in audit_log with incident_id and correlation_id.
- Keep agent outputs deterministic where possible by requiring strict JSON outputs.

## Prompt Contract Requirements

Every production prompt should define:
- Goal and scope
- Required input fields
- JSON output schema
- Failure behavior when evidence is insufficient
- Safety and redaction requirements

## Evaluation Requirements

- Add or update fixtures under tests/agent-evals/fixtures.
- Add deterministic tests that validate output shape and safety expectations.
- Keep eval data scrubbed and free of secrets.
