# Phase 32 — Provider Abstraction + Deployment Profiles

## Goal

Introduce a provider abstraction layer so RemediAI remains Azure/Foundry-optimized by default while supporting a portable profile for non-Azure Kubernetes clusters.

This phase defines interfaces, configuration, and deployment profile contracts for LLM, retrieval, identity/auth, and ticket/SCM integrations without changing agent business logic.

---

## Deliverables

| Artifact | Description |
|---|---|
| `packages/integrations/providers/base.py` | Provider protocols (`LLMProvider`, `RetrievalProvider`, `TicketProvider`, `SCMProvider`) |
| `packages/integrations/providers/registry.py` | Provider registry and runtime resolution by profile |
| `packages/integrations/providers/azure_foundry/` | Azure/Foundry default adapter implementations |
| `packages/integrations/providers/portable/` | Portable reference adapters (config-driven placeholders) |
| `apps/api/core/config.py` update | Profile and provider selection settings |
| `helm/remediai/values-azure-foundry.yaml` | Default Azure/Foundry profile values |
| `helm/remediai/values-portable.yaml` | Portable profile values |
| `docs/architecture/provider-model.md` | Provider model overview and boundaries |
| `tests/unit/test_provider_registry.py` | Provider resolution and validation tests |
| `tests/integration/test_profile_bootstrap.py` | Profile startup and adapter wiring tests |

---

## Configuration Contract

Add profile settings:

- `REMEDIAI_PROFILE`: `azure-foundry` (default) | `portable`
- `LLM_PROVIDER_ID`: provider key for current profile
- `RETRIEVAL_PROVIDER_ID`: provider key for current profile
- `SCM_PROVIDER_ID`: provider key for current profile
- `TICKET_PROVIDER_ID`: provider key for current profile

Rules:

1. `azure-foundry` is default when unset.
2. `portable` must start without Azure-specific mandatory values.
3. Invalid provider combinations fail fast at startup.
4. Agent runtime consumes provider protocols only.

Additional runtime resolution rules:

5. `SCM_PROVIDER_ID=auto` resolves to `azure-devops` only when Azure DevOps
	repository settings are present; otherwise SCM is treated as unconfigured.
6. `TICKET_PROVIDER_ID=none` is a supported first-class mode and must not block
	incident analysis or PR planning flows.
7. `RETRIEVAL_PROVIDER_ID=none` is a supported first-class mode for local and
	portable execution and must not block incident analysis.
8. When SCM, ticketing, or retrieval is unconfigured, agent nodes must skip
	gracefully with traceable non-error outcomes instead of raising integration
	exceptions.

---

## Security Touchpoints

- New LLM call introduced? **No new call types**; existing agents continue to call LLM through adapters and must preserve `scrub()` behavior.
- Agent decision written? **Yes, unchanged requirement** — all agent decisions continue to append `AgentTraceEntry` and persist to `audit_log`.
- New credential introduced? **Yes (provider-dependent)** — all credentials come from `pydantic-settings`; Key Vault/secret manager required in production.
- New HTTP endpoint introduced? **No**.

This phase introduces runtime integration health metadata consumed by dashboard
contracts in Phase 12/14; endpoint authentication remains aligned with existing
dashboard API auth posture for the current environment.

---

## Acceptance Criteria

- `azure-foundry` profile boots and runs the existing pipeline without behavior regressions.
- `portable` profile boots with non-Azure provider settings and passes smoke startup checks.
- Agent modules no longer import cloud SDK classes directly; imports are isolated in provider adapter modules.
- `ruff`, `mypy --strict`, and tests pass for provider registry and profile bootstrap.
- Helm install docs show explicit profile selection with tested examples.
- `SCM_PROVIDER_ID=auto` resolves deterministically and is test-covered.
- `TICKET_PROVIDER_ID=none` keeps bug creation optional with no pipeline
	regression.
- `RETRIEVAL_PROVIDER_ID=none` keeps RAG optional with no pipeline regression.
- Missing SCM/ticket configuration results in explicit warnings consumable by
	API/UI layers.

---

## Out of Scope

- Implementing every cloud provider SDK in this phase.
- Replacing LangGraph orchestration.
- Multi-tenant quota accounting (follow-up phase).
