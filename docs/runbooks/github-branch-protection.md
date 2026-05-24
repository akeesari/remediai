# GitHub Branch Protection and Required Checks Runbook

## Purpose

Use this runbook to configure repository-level protections so that only validated code reaches main.

## Scope

This applies to GitHub-hosted repositories using the workflow in .github/workflows/ci.yml.

## Prerequisites

- Admin or maintainer access to the repository.
- CI workflow file already present on default branch.
- At least one successful CI run so checks appear in the branch rules UI.

## Configure Branch Protection

1. Open Settings > Branches in the repository.
2. Under Branch protection rules, create or edit the rule for main.
3. Enable Require a pull request before merging.
4. Set Required approvals to 1 or higher.
5. Enable Dismiss stale pull request approvals when new commits are pushed.
6. Enable Require status checks to pass before merging.
7. Enable Require branches to be up to date before merging.
8. Add the required checks listed below.
9. Enable Restrict who can push to matching branches, or enable Do not allow bypassing the above settings.
10. Save the rule.

## Required Checks

Select these jobs from CI workflow runs:

- Lint and format
- Typecheck
- Security scan
- Tests
- Frontend build

Optional checks for main push quality:

- Local compose smoke
- Docker build

## Validate Configuration

1. Open a test pull request with a small doc change.
2. Confirm all required checks are requested.
3. Confirm merge is blocked until checks are green and approval is present.
4. Push a new commit and verify stale approvals are dismissed.

## Troubleshooting

- If checks do not appear: run the CI workflow at least once on main and refresh the branch protection page.
- If job names changed: update required checks to the current workflow job names.
- If checks are pending forever: verify GitHub Actions is enabled for the repository and organization policy allows workflow runs.
