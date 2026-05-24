# Phase 21 — CI Pipeline: Azure DevOps Pipelines

## Goal

Define and implement the Azure DevOps Pipelines YAML configuration for
automated PR validation and main-branch CI.  Every pull request must pass
lint, typecheck, security scan, and tests before merge is permitted.

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
| `azure-pipelines.yml` | Main pipeline: PR validation + main branch CI |
| `azure-pipelines-release.yml` | Release pipeline: build images, push to ACR, update Helm values |
| `.azure/templates/python-ci.yml` | Reusable step template: install, lint, typecheck, test |
| `.azure/templates/frontend-ci.yml` | Reusable step template: npm install, tsc, build |
| `.azure/templates/security-scan.yml` | Reusable step template: pip-audit, npm audit, detect-secrets |
| `Makefile` update | `ci-local` target: runs all checks locally in the same order as the pipeline |

---

## Pipeline Stages

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

## Pipeline YAML Structure

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

---

## Branch Policy Requirements

Configure in Azure DevOps Repository Settings → Branch Policies → `main`:

- Require a minimum of 1 reviewer (excluding the PR author).
- Require all pipeline stages to pass before merge.
- Prohibit direct pushes to `main`.
- Require up-to-date branches before merge.

---

## `detect-secrets` Baseline

Run `detect-secrets scan > .secrets.baseline` once and commit the baseline
file.  CI runs `detect-secrets scan --baseline .secrets.baseline` and fails
if new secrets are found that are not in the baseline.

---

## Makefile Addition

```makefile
ci-local: lint typecheck check-prompts test ui-build
```

---

## Acceptance Criteria

- `azure-pipelines.yml` triggers on PR and main branch pushes.
- All 5 PR stages run and complete successfully on a clean branch.
- A deliberate ruff error causes Stage 1 to fail and blocks merge.
- A deliberate test failure causes Stage 4 to fail and blocks merge.
- Test results are published to Azure DevOps Test Plans on each run.
- `detect-secrets` scan fails when a test secret is introduced.
- `make ci-local` replicates the pipeline checks locally.

---

## Out of Scope

- AKS deployment from CI (Phase 23).
- Azure infrastructure provisioning (Phase 23).
- Environment-specific variable groups / Key Vault integration in pipelines.
- Scheduled nightly test runs.
