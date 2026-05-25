# Phase 30 — Public Documentation Site

## Goal

Publish RemediAI as a professional open-source product by building a
Docusaurus v3 documentation site hosted on GitHub Pages (free tier).
The site is the public face of the project — it must earn trust at first
glance from platform engineers, developers, and engineering leads evaluating
the tool. This spec is also written as a **reusable template** for future
projects; every project-specific value is marked and listed in the Template
Variables table at the end.

---

## Deliverables

### D1 — Docusaurus v3 Site

| Item | Detail |
|------|--------|
| Generator | Docusaurus v3 (`@docusaurus/core@3.10.1`) |
| Theme | `@docusaurus/preset-classic` with custom CSS variables |
| Location | `apps/docs/` in the monorepo |
| Build output | Static HTML — artifact uploaded by GitHub Actions |
| Node version | 20 LTS |
| TypeScript | Strict, via `@tsconfig/docusaurus` |

---

### D2 — GitHub Pages Deployment

| Item | Detail |
|------|--------|
| Hosting | GitHub Pages free tier |
| Live URL | `https://<GH_ORG>.github.io/<REPO_NAME>/` |
| Source | GitHub Actions (not the legacy branch source) |
| Deploy branch | `gh-pages` is **not** used — artifact is uploaded directly |
| Custom domain | Supported via `CNAME` file in `apps/docs/static/` (optional) |
| Deploy trigger | Push to `main` when `apps/docs/**` or `docs/**` changed, plus `workflow_dispatch` |
| Workflow file | `.github/workflows/docs.yml` |
| Permissions required | `pages: write`, `id-token: write`, `contents: read` |
| Concurrency | `group: pages`, `cancel-in-progress: true` |

**GitHub Pages must be enabled before the first deploy will succeed.**
See D10 for the exact enablement procedure.

---

### D3 — Site Structure

```
/                           Landing page (hero + feature grid + CTA)
/docs/intro                 What is <PRODUCT_NAME>?
/docs/getting-started/      Quick-start guide
  prereqs                   Prerequisites checklist
  installation              Clone, .env setup, docker compose up
  first-incident            Trigger a sample incident end-to-end
/docs/architecture/         System design
  overview                  High-level diagram (Mermaid)
  data-flow                 Sequence diagram: exception → bug
  data-model                Schema / ER diagram
  tech-stack                Stack table with rationale
/docs/agents/               Agent pipeline deep-dive
  pipeline                  LangGraph pipeline overview
  triage                    Triage Agent
  root-cause                Root Cause Agent
  code-context              Code Context Agent
  rag-retrieval             RAG Retrieval Agent
  fix-planner               Fix Planner Agent
  validation                Validation Agent
  pr-agent                  PR Agent + human approval gate
/docs/integrations/         Azure service setup guides
  azure-monitor             KQL connector + App Insights config
  azure-devops              ADO Repos + Boards auth + permissions
  azure-openai              Azure OpenAI / AI Foundry endpoint setup
  azure-ai-search           Index creation + RAG population
  azure-key-vault           Key Vault + Managed Identity setup
/docs/configuration/        Reference for all env vars and settings
/docs/security/             Security design
  principles                Zero-trust, human-in-the-loop, no auto-merge
  pii-scrubbing             How PII is removed before LLM calls
  identity                  Managed Identity + Workload Identity
  audit-log                 What is logged and where
/docs/api/                  REST API reference
/docs/contributing/         Developer guide
  dev-environment           Local setup, linting, tests
  branch-conventions        Branch naming + PR process
  phase-workflow            How phases work, spec-first rule
/docs/roadmap               Current milestones + phase status
/blog/                      Announce posts
```

---

### D4 — Landing Page Sections (9 required)

1. **Hero** — bold headline, value prop subtitle, live stats row, two CTAs: "Get Started" + "View on GitHub"
2. **Problem / Solution** — 2-column grid: "Before" (pain list) vs "After" (win list)
3. **Feature Grid** — 3-column, 9 feature cards with icon, title, description
4. **Architecture Diagram** — ASCII diagram inside a styled code block
5. **How It Works** — 2-column numbered step grid (12 steps)
6. **Technology Stack** — horizontal badge strip of all technologies
7. **Security Promise** — 4-column grid of security pillars with icons
8. **CTA Section** — gradient banner with headline, sub-copy, two buttons
9. **Footer** (via Docusaurus config) — 3-column links, copyright, Apache 2.0 license link

---

### D5 — Visual Design System

| Element | Value |
|---------|-------|
| Primary colour | `#0078D4` (Azure blue) |
| Accent colour | `#8661C5` (agent purple) |
| Font | Inter 400/500/600/700/800 via Google Fonts |
| Dark mode | Enabled — `respectPrefersColorScheme: true` |
| Code highlighting | Prism: `python`, `typescript`, `bash`, `json`, `yaml`, `csharp`, `sql` |
| Diagrams | `@docusaurus/theme-mermaid` — rendered client-side |
| Admonitions | `:::tip`, `:::warning`, `:::danger`, `:::info` used throughout |
| Logo | Dual SVG (`logo.svg` light / `logo-dark.svg` dark) with product name |

---

### D6 — Search

- **Implementation:** `@easyops-cn/docusaurus-search-local` v0.44+
  - No API key, no external service, works fully on GitHub Pages
  - `hashed: true` — prevents filename leakage
  - Indexes docs, blog, and pages
- **Future upgrade path:** Algolia DocSearch (free for OSS after site is indexed) — commented-out config placeholder in `docusaurus.config.ts`

---

### D7 — SEO & Social Sharing

| Asset | Detail |
|-------|--------|
| `og:image` | `static/img/social-card.svg` (1200×630 SVG) + note to export PNG for max compatibility |
| `og:title` | Set in `docusaurus.config.ts` metadata block |
| `og:description` | 160-char product summary |
| `twitter:card` | `summary_large_image` |
| `sitemap.xml` | Auto-generated by `@docusaurus/plugin-sitemap` (bundled in preset) |
| Canonical URL | Set via `url` + `baseUrl` in config — no extra plugin needed |
| Trailing slash | `trailingSlash: false` — avoids double-redirect on GitHub Pages |
| Announcement bar | Closeable banner pointing to the roadmap page |

---

### D8 — GitHub Actions Workflow

File: `.github/workflows/docs.yml`

```
Trigger:
  push → main when paths: apps/docs/**, docs/**, .github/workflows/docs.yml
  workflow_dispatch (manual)

Permissions:
  contents: read
  pages: write
  id-token: write

Concurrency:
  group: pages
  cancel-in-progress: true

Jobs:
  build:
    runs-on: ubuntu-latest
    steps:
      1. actions/checkout@v4  (fetch-depth: 0 — needed for git history in blog)
      2. actions/setup-node@v4  (node-version: 20, cache: npm, cache-dependency-path: apps/docs/package-lock.json)
      3. npm ci  (working-directory: apps/docs)
      4. npm run build  (working-directory: apps/docs, NODE_ENV: production)
      5. actions/upload-pages-artifact@v3  (path: apps/docs/build)

  deploy:
    needs: build
    runs-on: ubuntu-latest
    environment:
      name: github-pages
      url: ${{ steps.deployment.outputs.page_url }}
    steps:
      1. actions/deploy-pages@v4
```

**Critical:** The `actions/upload-pages-artifact` step must point to the build
output directory, not the source directory.

---

### D9 — Content Migration

Migrate existing Markdown to Docusaurus pages. Phase specs are **not** published.

| Source file | Docusaurus page |
|-------------|----------------|
| `README.md` sections | Landing page + `/docs/intro` |
| `SPEC.md` | `/docs/architecture/data-model` + `/docs/integrations/*` |
| `ARCHITECTURE.md` | `/docs/architecture/overview` + `/docs/architecture/data-flow` |
| `AGENT_DESIGN.md` | `/docs/agents/*` |
| `TECH_STACK.md` | `/docs/architecture/tech-stack` |
| `SECURITY_GUARDRAILS.md` | `/docs/security/*` |
| `ROADMAP.md` | `/docs/roadmap` |
| `CONTRIBUTING.md` | `/docs/contributing/*` |
| `docs/specs/` | **Not published** — internal only |
| `docs/prompts/` | **Not published** — internal only |
| `docs/runbooks/` | **Not published** — internal only |

---

### D10 — GitHub Pages Enablement

This is a **one-time setup** that must be done before the first deployment.
It cannot be done by pushing code alone — it requires a repo admin action.

#### Method A — GitHub CLI (recommended, 30 seconds)

Prerequisites: `gh` CLI installed and authenticated (`gh auth login`).

```bash
# Enable GitHub Pages with GitHub Actions as the source
gh api repos/<GH_ORG>/<REPO_NAME>/pages \
  --method POST \
  --field build_type=workflow \
  --silent \
  && echo "GitHub Pages enabled — source: GitHub Actions" \
  || echo "Already enabled or insufficient permissions (check repo admin access)"
```

Verify:
```bash
gh api repos/<GH_ORG>/<REPO_NAME>/pages --jq '.status + " | url: " + .html_url'
```

Expected output: `enabled | url: https://<GH_ORG>.github.io/<REPO_NAME>/`

#### Method B — Browser UI (fallback)

1. Open `https://github.com/<GH_ORG>/<REPO_NAME>/settings/pages`.
2. Under **Build and deployment**, set **Source** to **GitHub Actions**.
3. Click **Save**.
4. No branch selection is needed — GitHub Actions manages the deployment.

#### Method C — Automated setup script

A setup script is provided at `scripts/setup_github_pages.sh` that:
- Checks if Pages is already enabled
- Enables it if not
- Verifies the live URL is reachable after deployment
- Prints next steps

Usage:
```bash
chmod +x scripts/setup_github_pages.sh
./scripts/setup_github_pages.sh
```

---

### D11 — Social Card (OG Image)

File: `apps/docs/static/img/social-card.svg`

Dimensions: 1200 × 630 px (standard OG image ratio)

Required elements:
- Background gradient matching the hero (`#0078D4` → `#005A9E` → `#8661C5`)
- Product name in white, large weight
- Tagline in white/semi-transparent
- URL in bottom-right corner
- No third-party fonts — use system-safe `sans-serif` in the SVG

**PNG export note:** Some social platforms (especially LinkedIn) do not render
SVG OG images. After the site is live, export the SVG to a 1200×630 PNG using:

```bash
# Requires Inkscape or rsvg-convert
rsvg-convert -w 1200 -h 630 apps/docs/static/img/social-card.svg \
  > apps/docs/static/img/social-card.png
```

Then update `docusaurus.config.ts` to reference `social-card.png` instead of
`social-card.svg` in the `image` field.

---

### D12 — `.nojekyll` File

File: `apps/docs/static/.nojekyll` (empty file)

**Why this is required:** GitHub Pages, by default, runs Jekyll processing on
static site uploads. Jekyll ignores any directory or file that starts with an
underscore (`_`). Docusaurus generates files and folders with underscore
prefixes (e.g., `_docusaurus/`). Without `.nojekyll`, these assets are silently
omitted and the site loads with broken CSS and JavaScript.

The `.nojekyll` file is placed in `static/` so Docusaurus copies it to the
build root during `npm run build`. It does not need any content — its presence
alone disables Jekyll.

---

### D13 — Deployment Execution (Push to Main)

This deliverable documents the exact process for committing Phase 30 code,
enabling GitHub Pages, pushing to `main`, and verifying the live site.
It is written as a repeatable procedure so it can be followed verbatim on
this project and adapted for future projects.

#### Pre-commit checklist

Before pushing, confirm all of the following locally:

| Check | Command | Expected result |
|-------|---------|-----------------|
| No broken internal links | `cd apps/docs && npm run build` | Exit 0, zero errors |
| Docs build output exists | `ls apps/docs/build/index.html` | File present |
| `.nojekyll` present | `ls apps/docs/static/.nojekyll` | File present (empty) |
| Workflow file valid YAML | `python3 -c "import yaml; yaml.safe_load(open('.github/workflows/docs.yml'))"` | No exception |
| `setup_github_pages.sh` executable | `ls -la scripts/setup_github_pages.sh` | `-rwxr-xr-x` |

#### Step 1 — Enable GitHub Pages (one-time, runs once per repo)

```bash
./scripts/setup_github_pages.sh
```

Expected final line: `Build type confirmed: GitHub Actions (workflow)`

If the script is not available or `gh` is not installed, use the browser:
`Settings → Pages → Source → GitHub Actions → Save`.

Verify enablement:

```bash
gh api repos/akeesari/remediai/pages --jq '.status + " | " + .html_url'
# Expected: enabled | https://akeesari.github.io/remediai/
```

#### Step 2 — Stage Phase 30 files

```bash
git add \
  .github/workflows/docs.yml \
  apps/docs/ \
  docs/runbooks/github-pages-setup.md \
  docs/specs/phase-30-documentation-site.md \
  scripts/setup_github_pages.sh
```

Verify staged files:

```bash
git diff --staged --stat
# Expected: ~47 files changed, ~6 000 insertions
```

#### Step 3 — Commit

Commit message format follows Conventional Commits (`docs` type, `site` scope):

```bash
git commit -m "docs(site): add Docusaurus documentation site and GitHub Pages deployment

- apps/docs/ — full Docusaurus v3 site (43 files, ~5 800 lines)
  - Landing page with 9 sections, Azure blue + agent purple design system
  - 35 documentation pages covering architecture, agents, integrations,
    security, API, contributing, and roadmap
  - Blog post: Introducing RemediAI
  - Local search via @easyops-cn/docusaurus-search-local
  - Mermaid diagram support, dark mode, OG social card
- .github/workflows/docs.yml — build + deploy workflow (Node 20, actions/deploy-pages@v4)
- scripts/setup_github_pages.sh — one-time GitHub Pages enablement script
- docs/runbooks/github-pages-setup.md — setup and troubleshooting runbook
- docs/specs/phase-30-documentation-site.md — full spec with reuse guide

Live at: https://akeesari.github.io/remediai/"
```

#### Step 4 — Push to main

```bash
git push origin main
```

This triggers the `docs.yml` workflow automatically because `apps/docs/**`
matches the path filter.

#### Step 5 — Monitor the workflow

```bash
# Watch the run live (blocks until complete)
gh run watch

# Or open in browser
gh run view --web
```

Expected output from a successful run:

```
✓ build     Build Docusaurus site   (1m 24s)
✓ deploy    Deploy to GitHub Pages  (0m 18s)

https://akeesari.github.io/remediai/
```

#### Step 6 — Post-deployment verification

Run each check after the workflow completes:

```bash
# 1. Site responds
curl -sI https://akeesari.github.io/remediai/ | grep "HTTP/"
# Expected: HTTP/2 200

# 2. OG meta tags present
curl -s https://akeesari.github.io/remediai/ \
  | grep -E 'og:(title|description|image)|twitter:card'
# Expected: 4 matching lines

# 3. Sitemap accessible
curl -sI https://akeesari.github.io/remediai/sitemap.xml | grep "HTTP/"
# Expected: HTTP/2 200

# 4. No Jekyll asset stripping (underscore-prefixed assets load)
curl -sI "https://akeesari.github.io/remediai/assets/js/main.js" \
  | grep "HTTP/"
# Expected: HTTP/2 200  (not 404)

# 5. Search index present
curl -s https://akeesari.github.io/remediai/search-index.json | head -c 80
# Expected: {"documents":[...
```

If all five pass, the site is live and fully functional.

#### Step 7 — Announce (optional)

Share the live URL:

```
https://akeesari.github.io/remediai/
```

The blog post "Introducing RemediAI" is already published at:

```
https://akeesari.github.io/remediai/blog/introducing-remediai
```

---

### D14 — Local Docker Development

The documentation site runs as a standalone Docker container so developers can
preview the exact production build locally before pushing to GitHub Pages.

#### Files

| File | Purpose |
|------|---------|
| `apps/docs/Dockerfile` | Multi-stage build: Node 20 (build) → Nginx 1.27 Alpine (serve) |
| `apps/docs/nginx.conf` | Nginx server block — serves build output at `/remediai/`, gzip enabled |

#### Dockerfile design

- **Build stage:** `node:20-alpine` — runs `npm ci` then `npm run build`
- **Production stage:** `nginx:1.27-alpine` — copies `build/` to `/usr/share/nginx/html/remediai/`
  so the container path matches the GitHub Pages `baseUrl: '/remediai/'`; no path rewriting needed.
- **Context:** `context: .` (monorepo root), matching the pattern used by all other services.

#### docker-compose.local.yml addition

```yaml
docs:
  build:
    context: .
    dockerfile: apps/docs/Dockerfile
  ports:
    - "${LOCAL_DOCS_PORT:-3001}:80"
```

Default port: `3001` (does not conflict with the dashboard on `3000`).
Override with `LOCAL_DOCS_PORT=<port>` in `.env.local`.

#### Usage

```bash
# Build and start only the docs container
docker compose -f docker-compose.local.yml up docs --build

# Open in browser
open http://localhost:3001/remediai/

# Rebuild after content changes
docker compose -f docker-compose.local.yml up docs --build --force-recreate

# Start everything including docs
docker compose -f docker-compose.local.yml up --build
```

#### Why the build runs inside Docker

Running `npm run build` inside the container catches issues that a local build
might miss: Node version differences and a clean `npm ci` (same as CI), not
the developer's local `node_modules`. The `npm ci` step uses the committed
`package-lock.json`, which is the same lock file the GitHub Actions CI uses.

#### Acceptance criteria for this deliverable

- `docker compose -f docker-compose.local.yml up docs --build` exits with code 0.
- `curl -sI http://localhost:3001/remediai/` returns `HTTP/1.1 200 OK`.
- `curl -sI http://localhost:3001/` returns `HTTP/1.1 301` redirecting to `/remediai/`.
- Static assets (`/remediai/assets/js/*.js`, `/remediai/assets/css/*.css`) return 200.
- Mermaid diagrams are visible on `http://localhost:3001/remediai/docs/architecture/overview`.

---

## File Layout (complete)

```
apps/docs/
  Dockerfile                  Multi-stage build: Node 20 build → Nginx 1.27 Alpine serve
  nginx.conf                  Nginx config: serves /remediai/, gzip, security headers
  docusaurus.config.ts        Site config, navbar, footer, plugins, SEO
  sidebars.ts                 Sidebar tree for /docs/*
  package.json                Dependencies and npm scripts
  package-lock.json           Committed lockfile — required for CI npm cache
  tsconfig.json               TypeScript config (extends @tsconfig/docusaurus)
  babel.config.js             Babel preset for Docusaurus
  static/
    .nojekyll                 Disables Jekyll processing on GitHub Pages (REQUIRED)
    img/
      logo.svg                Product SVG logo (light theme)
      logo-dark.svg           Product SVG logo (dark theme)
      social-card.svg         OG / Twitter social card (1200×630)
      favicon.ico             Favicon
    CNAME                     (optional) custom domain — e.g. docs.example.com
  src/
    css/
      custom.css              CSS variable overrides, layout, component styles
    pages/
      index.tsx               Landing page (all 9 sections inline)
  docs/
    intro.md
    getting-started/
      prereqs.md
      installation.md
      first-incident.md
    architecture/
      overview.md
      data-flow.md
      data-model.md
      tech-stack.md
    agents/
      pipeline.md
      triage.md
      root-cause.md
      code-context.md
      rag-retrieval.md
      fix-planner.md
      validation.md
      pr-agent.md
    integrations/
      azure-monitor.md
      azure-devops.md
      azure-openai.md
      azure-ai-search.md
      azure-key-vault.md
    configuration.md
    security/
      principles.md
      pii-scrubbing.md
      identity.md
      audit-log.md
    api.md
    contributing/
      dev-environment.md
      branch-conventions.md
      phase-workflow.md
    roadmap.md
  blog/
    authors.yml               Author profiles
    YYYY-MM-DD-slug.md        Announce post (use <!-- truncate --> for excerpt)
scripts/
  setup_github_pages.sh       One-time GitHub Pages enablement via gh CLI
docs/
  runbooks/
    github-pages-setup.md     Step-by-step runbook (CLI + browser + troubleshoot)
.github/
  workflows/
    docs.yml                  Build + deploy workflow
```

---

## Security Touchpoints

| Question | Answer |
|----------|--------|
| Does this phase make an LLM call? | No. |
| Does this phase write agent decisions? | No. |
| Does this phase introduce a new credential? | GitHub Actions uses the built-in `GITHUB_TOKEN` — no storage, no rotation needed. |
| Does this phase expose a new HTTP endpoint? | No — static site only. GitHub Pages serves it. |
| Are internal docs published? | Phase specs, prompt contracts, and runbooks are **not** in `apps/docs/` and are not published. |
| PII risk? | All example data must be synthetic. No real stack traces, customer names, or incident IDs in any published page or blog post. |
| Can someone exfiltrate secrets via the site? | No. The site is static HTML. It has no server-side code and makes no API calls. |

---

## Acceptance Criteria

### Build (local)
1. `npm run build` inside `apps/docs/` completes with zero errors and zero broken internal links.
2. `apps/docs/build/index.html` exists after build.
3. `apps/docs/static/.nojekyll` is committed (can be verified with `git ls-files apps/docs/static/.nojekyll`).

### GitHub Pages enablement
4. `gh api repos/<GH_ORG>/<REPO_NAME>/pages --jq '.status'` returns `enabled`.
5. `gh api repos/<GH_ORG>/<REPO_NAME>/pages --jq '.build_type'` returns `workflow`.

### Deployment
6. The `docs.yml` GitHub Actions workflow completes with all jobs green on push to `main`.
7. `curl -sI https://<GH_ORG>.github.io/<REPO_NAME>/` returns `HTTP/2 200`.

### Content and UX
8. Landing page renders all 9 sections in both light and dark modes.
9. All sidebar links resolve — no 404s anywhere in the doc tree.
10. Search returns results for at least 4 key terms from the product domain.
11. Mermaid diagrams render on `/docs/architecture/overview` and `/docs/agents/pipeline`.

### SEO and sharing
12. `curl -s https://<GH_ORG>.github.io/<REPO_NAME>/ | grep 'og:title'` returns a non-empty match.
13. `og:description` and `twitter:card` meta tags are present on the landing page.
14. `https://<GH_ORG>.github.io/<REPO_NAME>/sitemap.xml` returns HTTP 200.

### Asset integrity
15. `curl -sI https://<GH_ORG>.github.io/<REPO_NAME>/assets/js/main.js` returns HTTP 200 (Jekyll not stripping `_`-prefixed assets).
16. `search-index.json` is accessible (confirms local search index was built).

### Content safety
17. No secrets, real PII, or internal-only content (phase specs, prompt contracts) appears on the published site.
18. Blog post excerpt is correctly truncated at `<!-- truncate -->` on the blog index page.

---

## Out of Scope

- Versioned docs — add when v1.0 ships.
- Algolia DocSearch activation — placeholder config is commented in; activate after Algolia crawls the live site.
- i18n / translations.
- API reference auto-generation from OpenAPI JSON — manual endpoint tables for now.
- Authentication-gated pages.
- Blog comments or newsletter integration.
- Custom domain SSL — GitHub Pages handles it automatically when `CNAME` is added.
- Paid CDN or hosting upgrade.

---

## npm Dependencies

| Package | Version | Purpose |
|---------|---------|---------|
| `@docusaurus/core` | `3.10.1` | Core framework |
| `@docusaurus/preset-classic` | `3.10.1` | Docs + blog + pages + sitemap |
| `@docusaurus/theme-mermaid` | `3.10.1` | Mermaid diagram rendering |
| `@easyops-cn/docusaurus-search-local` | `^0.44` | Offline full-text search |
| `@mdx-js/react` | `^3.0` | MDX component support |
| `clsx` | `^2` | Conditional classnames |
| `prism-react-renderer` | `^2.3` | Code block syntax highlighting |
| `react` / `react-dom` | `^18` | React peer dependency |

Dev:

| Package | Version |
|---------|---------|
| `@docusaurus/module-type-aliases` | `3.10.1` |
| `@docusaurus/types` | `3.10.1` |
| `@tsconfig/docusaurus` | `^2.0` |
| `typescript` | `~5.4.5` |

---

## Implementation Notes

- `trailingSlash: false` in `docusaurus.config.ts` avoids double-redirect on GitHub Pages.
- `fetch-depth: 0` in the `checkout` step is required so Docusaurus can read git history for last-updated dates on doc pages.
- `cache-dependency-path: apps/docs/package-lock.json` is needed because the monorepo root also has a `package-lock.json` (or `pyproject.toml`); without this, the node cache key misses.
- The `github-pages` environment in the deploy job enables the "Deployments" UI in the GitHub repo — shows live URL and deployment history.
- Blog post front matter requires `authors`, `tags`, and `slug` fields; `<!-- truncate -->` controls the excerpt boundary.
- The `announcementBar` in themeConfig should link to an internal page (not an external URL) so it does not trigger cross-origin warnings.

---

## Reuse Guide for Future Projects

To adapt this phase for a new project, replace every occurrence of the
template variables below. All substitutions are mechanical — no structural
changes to the workflow, CSS, or content patterns are needed.

### Template Variables

| Variable | RemediAI value | Replace with |
|----------|---------------|-------------|
| `<GH_ORG>` | `akeesari` | Your GitHub organisation or username |
| `<REPO_NAME>` | `remediai` | Your repository name |
| `<PRODUCT_NAME>` | `RemediAI` | Your product name |
| `<PRODUCT_TAGLINE>` | `AI-powered exception analysis and remediation for enterprise .NET applications on Azure.` | Your one-sentence value proposition |
| `<PRODUCT_DESCRIPTION>` | (160-char OG description) | Your SEO meta description |
| `<PRIMARY_COLOR>` | `#0078D4` | Your brand primary colour |
| `<ACCENT_COLOR>` | `#8661C5` | Your accent / secondary colour |
| `<LOGO_SVG>` | `static/img/logo.svg` | Your product SVG logo |
| `<SOCIAL_CARD>` | `static/img/social-card.svg` | Your OG image |
| `<EDIT_URL>` | `https://github.com/akeesari/remediai/tree/main/apps/docs/` | Your repo tree URL |
| `<DOCS_BASE_PATH>` | `apps/docs/` | Path to the docs app in your monorepo |
| `<NODE_CACHE_PATH>` | `apps/docs/package-lock.json` | Path to the lock file for the cache key |
| `<BASEURL>` | `/remediai/` | `/<REPO_NAME>/` (must include trailing slash) |
| `<LIVE_URL>` | `https://akeesari.github.io/remediai/` | `https://<GH_ORG>.github.io/<REPO_NAME>/` |

### Steps to reuse

1. Copy `apps/docs/` to the new project's monorepo root.
2. Replace all template variables in `docusaurus.config.ts` and `package.json`.
3. Update `sidebars.ts` to match the new project's doc structure.
4. Replace content in `docs/` with the new project's documentation.
5. Update the landing page sections in `src/pages/index.tsx` (features, workflow steps, tech stack, security pillars).
6. Replace `static/img/logo.svg` and `static/img/social-card.svg` with new branding.
7. Update `blog/authors.yml` with the new project's author profiles.
8. Copy `.github/workflows/docs.yml` and update `apps/docs/` paths if the docs live elsewhere.
9. Run `scripts/setup_github_pages.sh` (after updating the org/repo values) to enable GitHub Pages.
10. Push to `main` — the site deploys automatically.

### What does NOT need to change

- CSS architecture (`custom.css` uses CSS variables — only the token values change)
- GitHub Actions workflow structure (only path filters may need updating)
- Docusaurus config structure (only values change, not the shape)
- `.nojekyll` requirement (always needed for any GitHub Pages + Docusaurus project)
- Search plugin config (zero-configuration for any project)
- `babel.config.js` and `tsconfig.json` (project-agnostic)
