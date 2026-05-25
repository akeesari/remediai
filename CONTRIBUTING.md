# Contributing to RemediAI

Thank you for your interest in contributing to RemediAI.

---

## Table of Contents

- [Code of Conduct](#code-of-conduct)
- [Getting Started](#getting-started)
- [Development Environment](#development-environment)
- [Branch Conventions](#branch-conventions)
- [Commit Messages](#commit-messages)
- [Pull Request Process](#pull-request-process)
- [Coding Standards](#coding-standards)
- [Testing](#testing)
- [Reporting Issues](#reporting-issues)
- [Security Vulnerabilities](#security-vulnerabilities)

---

## Code of Conduct

This project follows a standard contributor code of conduct. Be respectful, inclusive, and constructive. Harassment or abusive behaviour in issues, PRs, or discussions will not be tolerated.

---

## Getting Started

1. Fork the repository and clone your fork.
2. Read [ARCHITECTURE.md](ARCHITECTURE.md) for the system design.
3. Read [SPEC.md](SPEC.md) for functional requirements.
4. Read [AGENT_DESIGN.md](AGENT_DESIGN.md) if you are working on the agent pipeline.
5. Set up your local development environment (see below).

---

## Development Environment

### Prerequisites

- Python 3.12+
- Node.js 20+
- Docker Desktop (for local dependencies)
- An Azure subscription for testing Azure integrations (use a non-production subscription)
- Azure CLI (`az`) authenticated

### Python setup

```bash
# From the repo root
python -m venv .venv
source .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install poetry
poetry install
```

### Frontend setup

```bash
cd apps/dashboard
npm install
```

### Local full stack

Start the full stack (PostgreSQL, Redis, API, worker, dashboard, docs, and the local log bridge):

```bash
cp -n .env.example .env || true
make local-up
```

Useful local stack commands:

```bash
make local-logs
make local-migrate
make local-smoke
make local-down
```

### Environment variables

Copy `.env.example` to `.env` and fill in values for your non-production Azure resources and local port overrides. Never commit `.env`.

### Run the API

```bash
cd apps/api
uvicorn main:app --reload
```

### Run the dashboard

```bash
cd apps/dashboard
npm run dev
```

### Run tests

```bash
# Python unit + integration tests
pytest

# Frontend tests
cd apps/dashboard && npm test
```

---

## Branch Conventions

| Branch prefix   | Purpose                                         |
| --------------- | ----------------------------------------------- |
| `feature/`      | New features                                    |
| `fix/`          | Bug fixes                                       |
| `chore/`        | Maintenance, dependency updates, tooling        |
| `docs/`         | Documentation only changes                     |
| `refactor/`     | Code restructuring without behaviour change     |
| `test/`         | Adding or improving tests                       |

Branch names should be lowercase with hyphens: `feature/rag-retrieval-agent`.

---

## Commit Messages

Follow the [Conventional Commits](https://www.conventionalcommits.org/) format:

```
<type>(<scope>): <short description>

[optional body]

[optional footer]
```

Examples:

```
feat(agent): add root cause agent with structured JSON output
fix(ingestion): handle null stack trace in fingerprint hash
docs(architecture): update component diagram
chore(deps): bump langchain-openai to 0.2.x
```

Types: `feat`, `fix`, `docs`, `chore`, `refactor`, `test`, `perf`, `ci`

---

## Pull Request Process

1. Ensure your branch is up to date with `main` before opening a PR.
2. Open a draft PR early if you want feedback on direction.
3. Fill in the PR template (title, summary, test plan).
4. All CI checks must pass (lint, type check, tests).
5. At least one approving review is required before merge.
6. Squash-merge into `main` — keep the commit history clean.
7. Delete your branch after merge.

### GitHub Branch Protection (Recommended)

When this repository is hosted on GitHub, configure branch protection for
`main` to enforce CI quality gates:

1. Require at least 1 approving review.
2. Require status checks before merging.
3. Require branches to be up to date before merging.
4. Block direct pushes to `main`.

Recommended required checks (from `.github/workflows/ci.yml`):

- `Lint and format`
- `Typecheck`
- `Security scan`
- `Tests`
- `Frontend build`

Detailed setup steps are documented in
`docs/runbooks/github-branch-protection.md`.

### Copilot Customizations

RemediAI includes Copilot acceleration assets to keep implementation consistent and fast:

- Repository-wide policies: `.github/copilot-instructions.md`
- Scoped instruction layers: `.github/instructions/`
- Versioned prompt contracts: `docs/prompts/*_v*.md`
- Prompt validation script: `scripts/validate_prompt_contracts.py`

Recommended local setup:

```bash
# Validate prompt contracts
make check-prompts
```

### PR Checklist

- [ ] Tests added or updated for the changed behaviour
- [ ] `mypy` passes with no new errors
- [ ] `ruff` passes with no new violations
- [ ] `make check-prompts` passes for prompt or agent behavior changes
- [ ] No secrets or credentials committed
- [ ] Documentation updated if behaviour changed
- [ ] CHANGELOG updated if this is a user-facing change

---

## Coding Standards

### Python

- Python 3.12+ syntax; use `match/case` where appropriate.
- Type hints on all function signatures.
- Pydantic v2 models for all data structures crossing service or layer boundaries.
- SQLAlchemy 2.0 async ORM; no raw SQL except for migrations.
- No hardcoded secrets — use `pydantic-settings` and environment variables.
- Structured logging via `structlog` with `correlation_id` and `incident_id` in every log record.
- Run `ruff check .` and `ruff format .` before committing.
- Run `mypy --strict` and resolve all errors.

### TypeScript / React

- TypeScript strict mode enabled.
- React functional components with hooks only — no class components.
- `@tanstack/react-query` for all server state; no raw `useEffect` for data fetching.
- Tailwind CSS for styling; avoid inline styles.
- Run `eslint` and `tsc --noEmit` before committing.

### General

- No `TODO` comments in merged code — open an issue instead.
- One concern per file / module.
- Keep integrations (Azure clients) isolated in `packages/integrations/`.
- Keep agent prompts versioned in `docs/prompts/`.
- Keep prompt contracts explicit: Goal, Required Input, Output Contract, Failure Policy, Safety Rules.

---

## Testing

### Python

| Layer             | Framework                  | Location                    |
| ----------------- | -------------------------- | --------------------------- |
| Unit tests        | pytest                     | `tests/unit/`               |
| Integration tests | pytest + mock Azure clients| `tests/integration/`        |
| Agent evals       | pytest + eval fixtures     | `tests/agent-evals/`        |
| E2E               | pytest + live Azure env    | `tests/e2e/`                |

Integration tests use mock Azure clients — they do not require a live Azure subscription to run in CI.

E2E tests require a non-production Azure environment and are gated manually.

### Prompt Contract Validation

Prompt contracts are validated with:

```bash
python scripts/validate_prompt_contracts.py
pytest tests/agent-evals -v
```

Use this whenever prompt files in `docs/prompts/` or agent behavior contracts change.

### TypeScript

| Layer      | Framework              | Location                       |
| ---------- | ---------------------- | ------------------------------ |
| Unit tests | Vitest + Testing Library| `apps/dashboard/src/__tests__/`|

---

## Reporting Issues

Use GitHub Issues with the appropriate label:

- `bug` — something is broken
- `enhancement` — new feature request
- `documentation` — docs gap or error
- `question` — general question

For bugs, include: environment, steps to reproduce, expected vs actual behaviour, and relevant logs (scrubbed of any PII or secrets).

---

## Security Vulnerabilities

Do **not** open a public issue for security vulnerabilities. See [SECURITY.md](SECURITY.md) for the responsible disclosure process.
