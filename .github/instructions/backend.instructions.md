---
applyTo: "apps/api/**/*.py,apps/worker/**/*.py,packages/**/*.py,tests/**/*.py"
---

# Backend Implementation Rules

- Follow the MVP sequence in ROADMAP.md and relevant docs/specs/phase-*.md file.
- Keep function and method signatures fully typed.
- Use Pydantic v2 for cross-layer models and payload contracts.
- Keep Azure clients inside packages/integrations and inject them into services.
- Keep business logic out of FastAPI routers; routers should coordinate and return typed responses.
- Prefer small, composable modules over large files.
- Add or update tests in tests/unit or tests/integration for every behavior change.

## Required Validation Before Declaring Done

- ruff check .
- mypy apps/ packages/ --strict
- pytest tests/ -x -v

## Documentation Sync

When behavior, contracts, architecture, or setup changes, update the matching docs in the same change set:
- SPEC.md
- ARCHITECTURE.md
- AGENT_DESIGN.md
- TECH_STACK.md
- SECURITY_GUARDRAILS.md
- CONTRIBUTING.md
- ROADMAP.md
