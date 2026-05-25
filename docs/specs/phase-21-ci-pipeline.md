# Phase 21 — CI Pipelines: Azure DevOps + GitHub Actions

## Goal

Define and implement CI pipeline configuration for both Azure DevOps Pipelines
and GitHub Actions to support automated PR validation and main-branch CI.
Every pull request must pass lint, typecheck, security scan, and tests before
merge is permitted.

---

## Dependencies

Phase 20 (Local Full-Stack Docker Compose) must be complete before this
phase.  The Dockerfiles at `apps/api/Dockerfile`, `apps/worker/Dockerfile`,
and `apps/dashboard/Dockerfile` are created in Phase 20 and referenced by
Stage 6 (Docker Build) of the main branch CI pipeline.

---

## Deliverables

| Artifact | Description |
|---|---|
| `azure-pipelines.yml` | Main Azure DevOps pipeline: PR validation + main branch CI |
| `azure-pipelines-release.yml` | Azure DevOps release pipeline: build images, push to ACR, update Helm values |
| `.github/workflows/ci.yml` | GitHub Actions CI workflow: PR validation + main branch CI |
| `.github/workflows/release.yml` | GitHub Actions release workflow: build images and push to GitHub Container Registry |
| `.azure/templates/python-ci.yml` | Reusable step template: install, lint, typecheck, test |
| `.azure/templates/frontend-ci.yml` | Reusable step template: npm install, tsc, build |
| `.azure/templates/security-scan.yml` | Reusable step template: pip-audit, npm audit, detect-secrets |
| `Makefile` update | `ci-local` target: runs all checks locally in the same order as the pipeline |
| `.pre-commit-config.yaml` | pre-commit hook config: runs `ruff check`, `ruff format`, and `mypy --strict` on every local commit |
| `Makefile` `install-hooks` target | installs the pre-commit hooks into the local git repo |

---

## Pipeline Stages (Shared)

### PR Validation Pipeline (trigger: PR to `main`)

```
Stage 1: Lint & Format
  - ruff check .
  - ruff format --check .

Stage 2: Type Check
  - mypy apps/ packages/ --strict

Stage 3: Security Scan
  - pip-audit (Python dependency CVE scan)
  - npm audit --audit-level=moderate (frontend dependencies)
  - detect-secrets scan --baseline .secrets.baseline

Stage 4: Tests
  - python scripts/validate_prompt_contracts.py
  - pytest tests/ -x -v --ignore=tests/e2e (unit + integration + agent-evals)

Stage 5: Frontend Build
  - cd apps/dashboard && npm install --legacy-peer-deps
  - npm run build
```

Stages run sequentially.  A failure in any stage blocks the PR.

### Main Branch CI (trigger: push to `main`)

Runs all PR validation stages, then additionally:

```
Stage 6: Docker Build
  - Build API image: apps/api/Dockerfile
  - Build Worker image: apps/worker/Dockerfile
  - Build Dashboard image: apps/dashboard/Dockerfile

Stage 7: Push to ACR
  - Tag images with git SHA and `latest`
  - Push to Azure Container Registry
  - Update Helm chart image tags in deployment repo
```

---

## Azure DevOps Pipeline YAML Structure

### `azure-pipelines.yml`

```yaml
trigger:
  branches:
    include: [main]
  paths:
    exclude: ['docs/**', '*.md']

pr:
  branches:
    include: [main]

pool:
  vmImage: ubuntu-latest

variables:
  PYTHON_VERSION: '3.12'
  NODE_VERSION: '20'

stages:
  - stage: lint
    jobs:
      - template: .azure/templates/python-ci.yml
        parameters: { step: lint }

  - stage: typecheck
    dependsOn: lint
    jobs:
      - template: .azure/templates/python-ci.yml
        parameters: { step: typecheck }

  - stage: security
    dependsOn: lint
    jobs:
      - template: .azure/templates/security-scan.yml

  - stage: test
    dependsOn: [typecheck, security]
    jobs:
      - template: .azure/templates/python-ci.yml
        parameters: { step: test }

  - stage: frontend
    dependsOn: []
    jobs:
      - template: .azure/templates/frontend-ci.yml
```

## GitHub Actions Workflow Structure

### `.github/workflows/ci.yml`

```yaml
name: CI

on:
  pull_request:
    branches: [main]
  push:
    branches: [main]

jobs:
  lint:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: '3.12'
      - run: pip install poetry && poetry install --no-interaction --no-root
      - run: poetry run ruff check . && poetry run ruff format --check .

  typecheck:
    needs: lint
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: '3.12'
      - run: pip install poetry && poetry install --no-interaction --no-root
      - run: poetry run mypy apps/ packages/ --strict

  security:
    needs: typecheck
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - run: pip install pip-audit detect-secrets
      - run: pip-audit
      - run: cd apps/dashboard && npm ci && npm audit --audit-level=moderate
      - run: detect-secrets-hook --baseline .secrets.baseline $(git ls-files)

  test:
    needs: security
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: '3.12'
      - run: pip install poetry && poetry install --no-interaction --no-root
      - run: poetry run python scripts/validate_prompt_contracts.py
      - run: poetry run pytest tests/ -x -v --ignore=tests/e2e

  frontend:
    needs: test
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-node@v4
        with:
          node-version: '20'
      - run: cd apps/dashboard && npm install --legacy-peer-deps && npm run build
```

### `.github/workflows/release.yml`

```yaml
name: Release

on:
  workflow_dispatch:
  push:
    tags:
      - 'v*'

jobs:
  release:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: docker/login-action@v3
        with:
          registry: ghcr.io
          username: ${{ github.actor }}
          password: ${{ secrets.GITHUB_TOKEN }}
      - uses: docker/build-push-action@v6
        with:
          context: .
          file: apps/api/Dockerfile
          push: true
          tags: ghcr.io/${{ github.repository_owner }}/remediai-api:${{ github.sha }}
```

### Python CI Template (`.azure/templates/python-ci.yml`)

```yaml
parameters:
  - name: step
    type: string

steps:
  - task: UsePythonVersion@0
    inputs:
      versionSpec: $(PYTHON_VERSION)

  - script: pip install poetry && poetry install
    displayName: Install Python dependencies

  - ${{ if eq(parameters.step, 'lint') }}:
    - script: ruff check . && ruff format --check .
      displayName: Ruff lint + format check

  - ${{ if eq(parameters.step, 'typecheck') }}:
    - script: mypy apps/ packages/ --strict
      displayName: mypy strict

  - ${{ if eq(parameters.step, 'test') }}:
    - script: python scripts/validate_prompt_contracts.py
      displayName: Validate prompt contracts
    - script: pytest tests/ -x -v --ignore=tests/e2e --junitxml=results/test-results.xml
      displayName: pytest (unit + integration + agent-evals; e2e excluded)
    - task: PublishTestResults@2
      inputs:
        testResultsFiles: results/test-results.xml
      condition: always()
```

---

## Service Connection Requirements

| Connection | Used by | Scope |
|---|---|---|
| Azure Container Registry | Release pipeline (Stage 7) | Push images |
| Azure Resource Manager | Release pipeline | Update AKS Helm release (Phase 23) |

Service connections are created in Azure DevOps Project Settings.  Names are
referenced via pipeline variables: `ACR_SERVICE_CONNECTION`, `ARM_SERVICE_CONNECTION`.

## GitHub Package Permissions

| Permission | Used by | Scope |
|---|---|---|
| `packages: write` | GitHub release workflow | Push container images to GHCR |
| `contents: read` | GitHub release workflow | Read source for image builds |

The release workflow uses the repository-scoped `GITHUB_TOKEN` to push images
to GHCR.

---

## Branch Policy Requirements

Configure in Azure DevOps Repository Settings → Branch Policies → `main`:

- Require a minimum of 1 reviewer (excluding the PR author).
- Require all pipeline stages to pass before merge.
- Prohibit direct pushes to `main`.
- Require up-to-date branches before merge.

For GitHub repositories, configure equivalent branch protection on `main` with:

- Minimum 1 approving review.
- Required status checks for CI jobs.
- Up-to-date branch requirement before merge.
- No direct pushes to `main`.

---

## `detect-secrets` Baseline

Run `detect-secrets scan > .secrets.baseline` once and commit the baseline
file.  CI runs `detect-secrets scan --baseline .secrets.baseline` and fails
if new secrets are found that are not in the baseline.

---

## Pre-Commit Hooks

Install `pre-commit` (via Poetry dev dependencies) and configure it to run `ruff check`, `ruff format`, and `mypy --strict` on every `git commit`. This catches lint, format, and type errors locally before they ever reach CI.

### `.pre-commit-config.yaml`

```yaml
repos:
  - repo: https://github.com/astral-sh/ruff-pre-commit
    rev: v0.11.12
    hooks:
      - id: ruff
        args: [--fix]
      - id: ruff-format

  - repo: local
    hooks:
      - id: mypy
        name: mypy strict
        entry: poetry run mypy apps/ packages/ --strict
        language: system
        types: [python]
        pass_filenames: false
```

The `mypy` hook uses `local` repo so it runs inside the project's own Poetry virtual environment, ensuring it sees all installed stubs and plugins (e.g. `sqlalchemy.ext.mypy.plugin`). The mypy `cache_dir` is set in `[tool.mypy]` to `/tmp/mypy_cache_remediai` to prevent cache files from being written into the working tree.

Developers install hooks once after cloning:

```bash
make install-hooks
# equivalent: poetry run pre-commit install
```

---

## Makefile Addition

```makefile
install-hooks:
	poetry run pre-commit install

ci-local: lint typecheck check-prompts test ui-build
```

---

## Acceptance Criteria

- `azure-pipelines.yml` triggers on PR and main branch pushes.
- `.github/workflows/ci.yml` triggers on PR and main branch pushes.
- All 5 PR stages run and complete successfully on a clean branch.
- A deliberate ruff error causes Stage 1 to fail and blocks merge.
- A deliberate test failure causes Stage 4 to fail and blocks merge.
- Test results are published to Azure DevOps Test Plans on each run.
- GitHub Actions publishes pytest artifacts for failed and successful runs.
- `detect-secrets` scan fails when a test secret is introduced.
- `make ci-local` replicates the pipeline checks locally.
- `make install-hooks` installs the pre-commit hooks without error.
- A commit containing a ruff violation is blocked locally by the pre-commit hook.
- A commit containing an unformatted file is blocked locally by the pre-commit hook.
- A commit introducing a mypy type error is blocked locally by the pre-commit hook.

---

## Out of Scope

- AKS deployment from CI (Phase 23).
- Azure infrastructure provisioning (Phase 23).
- Environment-specific variable groups / Key Vault integration in pipelines.
- Scheduled nightly test runs.
