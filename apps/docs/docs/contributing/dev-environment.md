---
sidebar_position: 1
title: Development Environment
---

# Development Environment

This guide sets up a complete local development environment for contributing to RemediAI.

---

## Prerequisites

| Tool | Version | Install |
|------|---------|---------|
| Python | 3.12+ | [python.org](https://www.python.org/downloads/) |
| Node.js | 20 LTS | [nodejs.org](https://nodejs.org/) |
| Docker Desktop | Latest | [docker.com](https://www.docker.com/products/docker-desktop/) |
| Azure CLI | 2.60+ | `brew install azure-cli` / [docs.microsoft.com](https://docs.microsoft.com/cli/azure/install-azure-cli) |
| Poetry | 1.8+ | `pip install poetry` |
| Git | 2.40+ | [git-scm.com](https://git-scm.com/) |

---

## Fork and clone

```bash
# Fork the repository on GitHub, then:
git clone https://github.com/<your-fork>/remediai.git
cd remediai
git remote add upstream https://github.com/akeesari/remediai.git
```

---

## Python setup

```bash
python -m venv .venv
source .venv/bin/activate       # Windows: .venv\Scripts\activate
pip install poetry
poetry install
```

Install pre-commit hooks:

```bash
pip install pre-commit
pre-commit install
```

The pre-commit hooks run `ruff`, `mypy`, and `detect-secrets` on every commit.

---

## Frontend setup

```bash
cd apps/dashboard
npm install
```

---

## Documentation site setup

```bash
cd apps/docs
npm install
npm run start         # Opens browser at http://localhost:3000/remediai/
```

---

## Environment variables

```bash
cp .env.example .env
```

Fill in your non-production Azure resource values. See [Configuration Reference](../configuration) for the full variable list.

---

## Start local dependencies

```bash
make local-up         # Starts PostgreSQL, Redis, API, worker, dashboard, docs, and log bridge
make local-migrate    # Runs Alembic migrations
make local-smoke      # Verifies all connections
```

---

## Start the services

```bash
# Terminal 1 — API
cd apps/api && uvicorn main:app --reload --port 8000

# Terminal 2 — Agent worker
cd apps/worker && python -m worker.main

# Terminal 3 — React dashboard
cd apps/dashboard && npm run dev
```

Or use the full local stack via Docker Compose:

```bash
make local-full-up    # Starts all services including API, worker, dashboard
```

---

## Running tests

```bash
# All Python tests
pytest

# With coverage
pytest --cov=packages --cov=apps --cov-report=term-missing

# Specific test file
pytest tests/unit/test_pii_scrubber.py -v

# Agent evaluations
pytest tests/agent-evals/ -v

# Frontend tests
cd apps/dashboard && npm test
```

---

## Linting and type checking

```bash
# Lint + format Python (must pass before commit)
ruff check .
ruff format .

# Type check Python (must pass before commit)
mypy --strict apps/ packages/

# Lint TypeScript
cd apps/dashboard && npm run lint

# Type check TypeScript
cd apps/dashboard && npx tsc --noEmit

# Validate prompt contracts
make check-prompts
```

---

## Useful make targets

| Target | Description |
|--------|-------------|
| `make local-up` | Start Docker dependencies |
| `make local-down` | Stop Docker dependencies |
| `make local-logs` | Stream Docker logs |
| `make local-migrate` | Run Alembic migrations |
| `make local-smoke` | Connectivity smoke test |
| `make local-full-up` | Start all services |
| `make check-prompts` | Validate prompt contracts |
| `make test` | Run all Python tests |
| `make lint` | Run ruff + mypy |

---

## IDE setup

### VS Code

Recommended extensions:

- Python (Microsoft)
- Pylance
- Ruff (Astral)
- mypy type checker
- ESLint
- Tailwind CSS IntelliSense
- Azure Tools

Settings (`.vscode/settings.json`):

```json
{
  "[python]": {
    "editor.defaultFormatter": "charliermarsh.ruff",
    "editor.formatOnSave": true
  },
  "mypy.runUsingActiveInterpreter": true
}
```

### PyCharm / IntelliJ

- Enable `ruff` as the external formatter for Python files.
- Enable mypy integration via the Mypy plugin.
