# RemediAI Agent Profiles (Copilot + Claude)

This file defines reusable autonomous agent behavior that works across tools.

## CI Greenkeeper (Autonomous)

### Purpose
Use this profile when GitHub Actions or Azure DevOps pipelines are failing and you want autonomous repair until green.

### Copilot Usage
- Open agent picker and select `CI Greenkeeper` from `.github/agents/ci-greenkeeper.agent.md`.
- Provide input like:
  - `Fix failing run https://github.com/<org>/<repo>/actions/runs/<id> and continue until green.`

### Claude Usage (Prompt Template)
Use this exact prompt in Claude:

```text
Act as RemediAI CI Greenkeeper.
Read and follow:
- docs/specs/phase-20-local-docker-compose.md
- docs/specs/phase-21-ci-pipeline.md
- .github/workflows/ci.yml
- .github/workflows/release.yml
- azure-pipelines.yml
- azure-pipelines-release.yml
- .github/copilot-instructions.md
- CLAUDE.md

Goal: Take this failing CI run and keep working autonomously until pipeline is green:
<PASTE_RUN_URL>

Rules:
- Do not stop between steps while deterministic actions exist.
- Reproduce failures locally, apply smallest safe fixes, rerun checks, and iterate.
- Commit, push, and monitor remote pipeline runs automatically.
- If a run fails after push, immediately continue fix cycles until green.
- Run at minimum:
  ruff check .
  mypy apps/ packages/ --strict
  pytest tests/ -q --ignore=tests/e2e
  plus failed stage equivalents.
- Keep GitHub and Azure pipeline intent aligned.
- Do not use destructive git operations.

Output each cycle:
1) root cause, 2) files changed, 3) command results, 4) blockers, 5) green-readiness status.
```

## Recommended Industry Practices for Autonomous CI Agents

1. Enforce fail-fast pipeline topology and short feedback loops.
2. Keep local CI parity (`make` targets) for every critical pipeline path.
3. Pin dependencies conservatively and upgrade only what the failure requires.
4. Use immutable artifacts and publish test/security reports for traceability.
5. Scope workflow permissions to least privilege.
6. Make fixes atomic and reversible (small commits, clear messages).
7. Prefer deterministic tooling (`--no-interaction`, lockfiles, fixed Python/Node versions).
8. Treat security scans as blocking gates, not advisory noise.
9. Maintain branch protection with required checks synced to real job names.
10. Document runbooks for human override and incident response.

## Dependency Security Greenkeeper (Autonomous)

### Purpose
Use this profile when CI fails specifically in dependency/security stages such as pip-audit, npm audit, or detect-secrets.

### Copilot Usage
- Select `Dependency Security Greenkeeper` from `.github/agents/dependency-security-greenkeeper.agent.md`.
- Provide input like:
  - `Fix this failing security stage and continue until green: <RUN_URL>`

### Claude Usage (Prompt Template)

```text
Act as RemediAI Dependency Security Greenkeeper.
Read and follow:
- docs/specs/phase-21-ci-pipeline.md
- .github/workflows/ci.yml
- azure-pipelines.yml
- pyproject.toml
- apps/dashboard/package.json
- apps/dashboard/package-lock.json
- .secrets.baseline
- .github/copilot-instructions.md
- CLAUDE.md

Goal: Resolve this failing security/dependency pipeline and continue iterating until green:
<PASTE_RUN_URL>

Rules:
- Do not stop while deterministic fixes exist.
- Prefer minimal safe upgrades; avoid broad forced updates.
- Commit and push once local security gates pass, then monitor and retry automatically if run fails.
- Run and pass: pip-audit, npm audit --audit-level=moderate, detect-secrets checks, then ruff/mypy/pytest.
- Never weaken security gates to force a pass.

Output each cycle:
1) root cause, 2) vulnerable deps + fixed versions, 3) files changed, 4) command results, 5) residual risk.
```
