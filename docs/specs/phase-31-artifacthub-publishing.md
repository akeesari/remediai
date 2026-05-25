# Phase 31 — Artifact Hub Publishing

## Goal

Publish RemediAI as a discoverable, installable package on
[Artifact Hub](https://artifacthub.io/) — the canonical registry for
cloud-native packages used by projects like Grafana, Loki, and ArgoCD.

At the end of this phase:

1. Docker images for all three services (API, Worker, Dashboard) are built and
   pushed to GitHub Container Registry (GHCR) on every release tag.
2. The Helm chart (`helm/remediai/`) is enriched with Artifact Hub metadata,
   packaged, and published to a Helm chart repository hosted on GitHub Pages.
3. `artifacthub-repo.yml` in the repo root ties the GitHub repository to the
   Artifact Hub listing.
4. A GitHub Actions release workflow automates the entire pipeline end-to-end.
5. The Artifact Hub listing shows the correct maintainer, description,
   screenshots, changelog, and category — matching the quality bar of Loki and
   ArgoCD listings.

---

## Background

Phase 23 defined the internal Helm chart structure (`helm/remediai/`) for AKS
deployment.  This phase extends that chart for **public distribution**, which
requires:

- A public OCI-compatible image registry (GHCR — free for public repos).
- A hosted Helm chart repository so `helm repo add remediai <url>` works.
- Artifact Hub metadata files that power the listing page.
- A repeatable, automated release workflow so every `git tag vX.Y.Z` produces a
  new chart version and updated images with no manual steps.

Phase 30 (Documentation Site) creates the GitHub Pages site at
`https://<org>.github.io/remediai/`. The chart repository will be hosted at
`https://<org>.github.io/remediai/charts/` — a sub-path of the same Pages
site — so both can share the same `gh-pages` branch without conflict.

---

## Deliverables

### D1 — Docker Images on GHCR

Three public images, all tagged `:latest` and `:<semver>`:

| Image | Source | GHCR path |
|-------|--------|-----------|
| API server | `apps/api/Dockerfile` | `ghcr.io/<org>/remediai-api` |
| Agent / ingestion worker | `apps/worker/Dockerfile` | `ghcr.io/<org>/remediai-worker` |
| React dashboard (nginx) | `apps/dashboard/Dockerfile` | `ghcr.io/<org>/remediai-dashboard` |

**Requirements:**

- Multi-stage builds (already required by Phase 23 security rules) — no dev
  dependencies in the final layer.
- Image labels follow the OCI annotation spec:
  ```dockerfile
  LABEL org.opencontainers.image.source="https://github.com/<org>/remediai"
  LABEL org.opencontainers.image.licenses="Apache-2.0"
  LABEL org.opencontainers.image.description="RemediAI — AI-powered incident analysis"
  ```
- Images are scanned by Trivy in CI; the workflow fails if any CRITICAL CVE is
  found.
- Images are multi-arch: `linux/amd64` and `linux/arm64` (built with
  `docker buildx`).

---

### D2 — Helm Chart Enrichment

Extend the existing chart at `helm/remediai/` with Artifact Hub metadata.

#### `helm/remediai/Chart.yaml` — full specification

```yaml
apiVersion: v2
name: remediai
description: >
  AI-powered incident analysis platform. Ingests exceptions from Azure Monitor,
  triages them with a LangGraph agent pipeline, and generates fix recommendations
  and draft pull requests — with a human approval gate at every step.
type: application
version: 0.1.0          # Helm chart version — bump on every chart change
appVersion: "0.1.0"     # Application version — matches the Git release tag

home: https://<org>.github.io/remediai/
icon: https://<org>.github.io/remediai/img/logo.svg
sources:
  - https://github.com/<org>/remediai

keywords:
  - ai
  - incident-management
  - llm
  - azure
  - langgraph
  - monitoring
  - devops
  - aiops

maintainers:
  - name: Anji Keesari
    email: anjkeesari@gmail.com
    url: https://github.com/anjkeesari

dependencies: []        # No sub-charts; all services are in the same chart

annotations:
  # Artifact Hub category — shown in the filter sidebar
  artifacthub.io/category: monitoring-logging

  # SPDX license identifier
  artifacthub.io/license: Apache-2.0

  # Rendered as the "Changelog" section on the listing page
  artifacthub.io/changes: |
    - kind: added
      description: Initial public release

  # Shown as screenshots in the listing gallery
  artifacthub.io/screenshots: |
    - title: Incident Dashboard
      url: https://<org>.github.io/remediai/img/screenshots/dashboard.png
    - title: Root Cause Analysis
      url: https://<org>.github.io/remediai/img/screenshots/root-cause.png
    - title: Fix Recommendation
      url: https://<org>.github.io/remediai/img/screenshots/fix-planner.png

  # Links shown in the "Links" section of the listing
  artifacthub.io/links: |
    - name: Documentation
      url: https://<org>.github.io/remediai/
    - name: GitHub
      url: https://github.com/<org>/remediai

  # Operator capability level (not an operator, but field is used broadly)
  # artifacthub.io/operator: "false"

  # Displayed in the "Security" tab if a security policy URL is present
  artifacthub.io/containsSecurityUpdates: "false"

  # Prerelease flag — set to "true" for pre-v1.0 releases
  artifacthub.io/prerelease: "true"

  # Signed chart verification (added after cosign signing is set up in D5)
  # artifacthub.io/signKey: |
  #   fingerprint: <cosign-public-key-fingerprint>
  #   url: https://github.com/<org>/remediai/blob/main/cosign.pub
```

#### `helm/remediai/README.md` — required for listing description

This file is rendered verbatim as the main body of the Artifact Hub listing
page. It must contain:

1. **Short description** — one paragraph, matches `Chart.yaml` description.
2. **Prerequisites** — Kubernetes ≥ 1.28, Helm ≥ 3.12, Azure subscription.
3. **Quick-start** — `helm repo add` + `helm install` commands with the
   minimum required values.
4. **Required values** — table of all values that have no default and must be
   supplied (Azure endpoints, Key Vault URI, image registry).
5. **Optional values** — table of tunable values with defaults shown.
6. **Upgrade notes** — how to run `helm upgrade`.
7. **Uninstall** — `helm uninstall` + any manual cleanup steps.
8. **Configuration reference** — full `values.yaml` parameter table.

#### `helm/remediai/values.yaml` — public-distribution defaults

The existing `values.yaml` (Phase 23) uses `remediai.azurecr.io` as the
registry. For public distribution, defaults must reference GHCR:

```yaml
global:
  registry: ghcr.io/<org>
  imageTag: "0.1.0"    # default — overridden at install time

api:
  image: remediai-api
  # ... rest unchanged from Phase 23

workerAgents:
  image: remediai-worker

dashboard:
  image: remediai-dashboard
```

---

### D3 — Artifact Hub Repository Metadata File

**File:** `artifacthub-repo.yml` (repo root — already checked for on every
Artifact Hub scan)

```yaml
# Artifact Hub repository ownership verification file.
# The repositoryID is assigned by Artifact Hub after registration (Step 5 in
# the Manual Steps section below). Commit the ID once obtained.
repositoryID: ""   # FILL IN after Artifact Hub registration

owners:
  - name: Anji Keesari
    email: anjkeesari@gmail.com
```

This file proves ownership and prevents repository hijacking. Artifact Hub
will reject listings where this file is missing or the `repositoryID` does not
match the registered repository.

---

### D4 — Helm Chart Repository on GitHub Pages

Artifact Hub needs a URL where it can fetch `index.yaml` to discover chart
versions. The chart repository is hosted alongside the documentation site on
GitHub Pages.

**Layout on the `gh-pages` branch:**

```
/                        (documentation site — Phase 30)
/charts/
  index.yaml             (Helm repo index — generated by helm repo index)
  remediai-0.1.0.tgz     (packaged chart)
  remediai-0.2.0.tgz     ...
```

**Registration URL used in Artifact Hub:**
`https://<org>.github.io/remediai/charts/`

**`helm repo add` command for users:**
```bash
helm repo add remediai https://<org>.github.io/remediai/charts/
helm repo update
helm install remediai remediai/remediai --namespace remediai --create-namespace \
  --set azureOpenAI.endpoint=<your-endpoint> \
  --set database.host=<your-postgres-host>
```

---

### D5 — GitHub Actions Release Workflow

**File:** `.github/workflows/release.yml`

Triggered by: push of a tag matching `v[0-9]+.[0-9]+.[0-9]+` (e.g. `v0.1.0`).
Can also be manually triggered via `workflow_dispatch` with a version input.

#### Jobs

```
release.yml
  ├── job: build-and-push-images
  │     Builds and pushes all three Docker images to GHCR
  │     Uses docker/build-push-action + docker/setup-buildx-action
  │     Scans each image with aquasecurity/trivy-action (CRITICAL fails build)
  │
  ├── job: package-and-publish-chart    (needs: build-and-push-images)
  │     Packages the Helm chart with helm package
  │     Updates helm/remediai/Chart.yaml version from the Git tag
  │     Appends the new .tgz to the gh-pages branch /charts/ directory
  │     Runs helm repo index --merge to update index.yaml
  │     Commits and pushes to gh-pages
  │
  └── job: create-github-release        (needs: package-and-publish-chart)
        Creates a GitHub Release with:
          - Auto-generated release notes from conventional commits
          - The packaged .tgz as a release asset
          - The CHANGELOG entry for this version
```

#### Detailed step-by-step for `build-and-push-images`

```yaml
- name: Log in to GHCR
  uses: docker/login-action@v3
  with:
    registry: ghcr.io
    username: ${{ github.actor }}
    password: ${{ secrets.GITHUB_TOKEN }}

- name: Set up QEMU (multi-arch)
  uses: docker/setup-qemu-action@v3

- name: Set up Docker Buildx
  uses: docker/setup-buildx-action@v3

- name: Extract version from tag
  id: version
  run: echo "VERSION=${GITHUB_REF_NAME#v}" >> $GITHUB_OUTPUT

- name: Build and push API image
  uses: docker/build-push-action@v5
  with:
    context: apps/api
    platforms: linux/amd64,linux/arm64
    push: true
    tags: |
      ghcr.io/${{ github.repository_owner }}/remediai-api:latest
      ghcr.io/${{ github.repository_owner }}/remediai-api:${{ steps.version.outputs.VERSION }}
    labels: |
      org.opencontainers.image.source=${{ github.server_url }}/${{ github.repository }}
      org.opencontainers.image.revision=${{ github.sha }}
      org.opencontainers.image.version=${{ steps.version.outputs.VERSION }}

# Repeat for remediai-worker and remediai-dashboard

- name: Scan API image for CVEs
  uses: aquasecurity/trivy-action@master
  with:
    image-ref: ghcr.io/${{ github.repository_owner }}/remediai-api:${{ steps.version.outputs.VERSION }}
    exit-code: '1'
    severity: CRITICAL
```

#### Detailed step-by-step for `package-and-publish-chart`

```yaml
- name: Checkout gh-pages branch
  uses: actions/checkout@v4
  with:
    ref: gh-pages
    path: gh-pages

- name: Update chart version in Chart.yaml
  run: |
    VERSION=${{ needs.build-and-push-images.outputs.version }}
    sed -i "s/^version:.*/version: ${VERSION}/" helm/remediai/Chart.yaml
    sed -i "s/^appVersion:.*/appVersion: \"${VERSION}\"/" helm/remediai/Chart.yaml

- name: Package Helm chart
  run: helm package helm/remediai/ --destination gh-pages/charts/

- name: Rebuild Helm repo index
  run: |
    helm repo index gh-pages/charts/ \
      --url https://${{ github.repository_owner }}.github.io/remediai/charts/

- name: Commit and push chart to gh-pages
  run: |
    cd gh-pages
    git config user.name "github-actions[bot]"
    git config user.email "github-actions[bot]@users.noreply.github.com"
    git add charts/
    git commit -m "chore: release chart v${VERSION}"
    git push
```

#### Required GitHub repository settings

| Setting | Value |
|---------|-------|
| Pages source | `gh-pages` branch, root `/` |
| Package visibility | Public (GHCR packages default to private — must be set to public after first push) |
| `GITHUB_TOKEN` permissions | `contents: write`, `packages: write`, `pages: write`, `id-token: write` |
| Branch protection on `gh-pages` | Allow force-push from `github-actions[bot]` only |

---

### D6 — Screenshot Assets

Three PNG screenshots (1280×800) stored at:

```
apps/docs/static/img/screenshots/
  dashboard.png       Incident list view with status / priority columns
  root-cause.png      Incident detail showing root cause summary and agent trace
  fix-planner.png     Fix recommendation panel with approval button
```

These are referenced from `Chart.yaml` annotations and rendered in the Artifact
Hub listing gallery. They must be committed to `main` before the first release
tag is pushed.

---

### D7 — CHANGELOG File

**File:** `CHANGELOG.md` (repo root)

Follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) format.
Used by the GitHub Release workflow to populate release notes.

Initial content:

```markdown
# Changelog

All notable changes to this project will be documented in this file.

## [Unreleased]

## [0.1.0] — 2026-05-25
### Added
- Initial public release
- Helm chart for AKS deployment
- Docker images for API, Worker, and Dashboard
- Artifact Hub listing
```

---

## Manual Steps (One-Time — Not Automated)

These steps cannot be automated and must be performed by a human once:

### Step 1 — Make the GitHub repository public

The repository must be public for GHCR images and GitHub Pages to be
accessible to external users without authentication.

Go to: `GitHub → Settings → Danger Zone → Change repository visibility → Public`

### Step 2 — Make GHCR packages public

After the first `release.yml` run, each of the three packages will exist in
GHCR as private. Make each public:

`GitHub → Packages → remediai-api → Package settings → Change visibility → Public`

Repeat for `remediai-worker` and `remediai-dashboard`.

### Step 3 — Enable GitHub Pages

`GitHub → Settings → Pages → Source: Deploy from branch → Branch: gh-pages → / (root)`

Verify that `https://<org>.github.io/remediai/charts/index.yaml` returns a
valid YAML document.

### Step 4 — Prepare screenshots

Create or export three PNGs from the running dashboard, place them at
`apps/docs/static/img/screenshots/` and commit to `main` before tagging.

### Step 5 — Register on Artifact Hub

1. Sign in to [artifacthub.io](https://artifacthub.io) with GitHub.
2. Navigate to: **Control Panel → Add repository**.
3. Fill in:
   - **Kind:** Helm chart
   - **Name:** `remediai`
   - **Display name:** RemediAI
   - **URL:** `https://<org>.github.io/remediai/charts/`
4. Copy the generated `repositoryID`.
5. Paste the `repositoryID` into `artifacthub-repo.yml` and commit to `main`.
6. Click **Trigger scan** — Artifact Hub will index the chart within minutes.
7. Verify the listing at `https://artifacthub.io/packages/helm/remediai/remediai`.

### Step 6 — Push the first release tag

```bash
git tag v0.1.0
git push origin v0.1.0
```

This triggers `release.yml` and starts the full pipeline.

---

## Security Touchpoints

| Question | Answer |
|----------|--------|
| Does this phase make an LLM call? | No. |
| Does this phase write agent decisions? | No. |
| Does this phase introduce a new credential? | No new credentials. `GITHUB_TOKEN` is built-in and scoped to the run. GHCR login uses `GITHUB_TOKEN` only. |
| Does this phase expose a new HTTP endpoint? | No new application endpoints. GitHub Pages serves static files. |
| Are Docker images public? | Yes — images are public on GHCR. They contain no secrets (secrets come from Key Vault at runtime). |
| Trivy scan | All three images are scanned for CRITICAL CVEs before the chart is published. The workflow fails if any are found. |
| `artifacthub-repo.yml` ownership | The `repositoryID` must match the registered repository, preventing listing hijacking. |
| OCI labels | `org.opencontainers.image.source` links each image back to this repository for supply-chain transparency. |

---

## Acceptance Criteria

1. `helm lint helm/remediai/` passes with zero errors and zero warnings.
2. `helm template helm/remediai/ --set global.imageTag=0.1.0` renders valid Kubernetes YAML with no missing required values.
3. `helm repo add remediai https://<org>.github.io/remediai/charts/ && helm repo update` succeeds.
4. `helm search repo remediai/remediai` returns the chart with the correct version and description.
5. `docker pull ghcr.io/<org>/remediai-api:0.1.0` succeeds from an unauthenticated machine.
6. `docker pull ghcr.io/<org>/remediai-worker:0.1.0` succeeds from an unauthenticated machine.
7. `docker pull ghcr.io/<org>/remediai-dashboard:0.1.0` succeeds from an unauthenticated machine.
8. Trivy scan reports zero CRITICAL CVEs on all three images.
9. Artifact Hub listing at `https://artifacthub.io/packages/helm/remediai/remediai` is visible without login.
10. Listing shows: correct description, maintainer name (Anji Keesari), license (Apache-2.0), category (Monitoring & Logging), at least one screenshot, and a working "Get install instructions" dialog.
11. `artifacthub-repo.yml` is present in the repo root with a non-empty `repositoryID`.
12. `CHANGELOG.md` exists and contains the `[0.1.0]` entry.
13. The GitHub Release for `v0.1.0` exists with the `.tgz` chart as an asset.
14. Multi-arch images: `docker manifest inspect ghcr.io/<org>/remediai-api:0.1.0` shows both `amd64` and `arm64` manifests.

---

## Out of Scope

- Helm chart signing with cosign (supply-chain hardening — add in a follow-up phase).
- Algolia / DocSearch for Artifact Hub listing (not configurable by publishers).
- OCI-format chart publishing (traditional `index.yaml` repo is sufficient for Artifact Hub; OCI can be added later).
- Semantic versioning automation (conventional-commits bot, release-please) — versions are set manually for now.
- Multiple chart variants (e.g. `remediai-minimal` without the dashboard) — single chart only.
- Helm chart submission to the official `helm/charts` repository — Artifact Hub is the target, not the legacy charts repo.
- ArtifactHub verified publisher badge — requires domain verification; add after the documentation site domain is confirmed.

---

## Dependencies

| Dependency | Used in | Notes |
|------------|---------|-------|
| `docker/build-push-action@v5` | D5 release workflow | Multi-arch image build + push |
| `docker/setup-buildx-action@v3` | D5 release workflow | Required for `linux/arm64` |
| `docker/setup-qemu-action@v3` | D5 release workflow | Required for cross-compilation |
| `docker/login-action@v3` | D5 release workflow | GHCR auth |
| `aquasecurity/trivy-action@master` | D5 release workflow | CVE scanning |
| `actions/checkout@v4` | D5 release workflow | |
| `helm` CLI ≥ 3.12 | D4, D5 | `helm package`, `helm repo index` |
| Phase 23 | Helm chart structure | `helm/remediai/` already exists |
| Phase 30 | `gh-pages` branch | Chart repo shares the Pages site |

---

## File Checklist

Files created or modified by this phase:

| Status | Path | Description |
|--------|------|-------------|
| `[new]` | `artifacthub-repo.yml` | Artifact Hub ownership verification |
| `[new]` | `CHANGELOG.md` | Keep a Changelog format |
| `[new]` | `.github/workflows/release.yml` | Full release pipeline |
| `[modified]` | `helm/remediai/Chart.yaml` | Add ArtifactHub annotations, maintainer, keywords |
| `[modified]` | `helm/remediai/values.yaml` | Change default registry from ACR to GHCR |
| `[new]` | `helm/remediai/README.md` | Listing description + install guide |
| `[new]` | `apps/docs/static/img/screenshots/dashboard.png` | Screenshot asset |
| `[new]` | `apps/docs/static/img/screenshots/root-cause.png` | Screenshot asset |
| `[new]` | `apps/docs/static/img/screenshots/fix-planner.png` | Screenshot asset |
| `[modified]` | `apps/api/Dockerfile` | Add OCI labels |
| `[modified]` | `apps/worker/Dockerfile` | Add OCI labels |
| `[modified]` | `apps/dashboard/Dockerfile` | Add OCI labels |
