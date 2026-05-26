# Production Readiness Action Plan

**Review date:** 2026-05-25
**Reviewer:** Solution Architect (Python + React)
**Branch at review time:** `main` (phases 1–21, 30, 32, 33 complete)

This document tracks every corrective action identified in the production-grade architecture
review. Items are grouped by priority tier. Work through P0 before P1; H1 is a prerequisite
for several items in P1 and P2 and should be done first within that tier.

---

## How to use this document

Each item contains:
- **Problem** — what is wrong and why it matters in production
- **Files** — exact file paths and line numbers
- **Fix** — concrete, copy-paste-level implementation guidance
- **Depends on** — items that must be completed first
- **Effort** — rough estimate (S = < 1 hour, M = 1–4 hours, L = half-day+)

Mark items complete by checking the box: `- [x]`

---

## P0 — CRITICAL (block production deploy)

These five items must be resolved before any production deployment. They represent
active security risks in the current state.

---

### C1. Sensitive config fields stored as plain `str` — must be `SecretStr`

- [ ] **Status:** Open

**Problem:**
Four fields in `Settings` hold secrets but use Python `str`. This means the values
appear in plaintext in log output, tracebacks, `model_dump()` serialization, and
any debug endpoint that prints the settings object. `pydantic-settings` provides
`SecretStr` exactly for this case — it renders as `**********` in all string
representations.

**Files:**
- [`apps/api/core/config.py`](../apps/api/core/config.py) — lines 19, 39, 46, 53

```python
# CURRENT (unsafe)
postgres_password: str = "change_me_locally"   # line 19
portable_openai_api_key: str = ""              # line 39
azure_devops_pat: str = ""                     # line 46
azure_search_api_key: str = ""                 # line 53
```

**Fix:**

Step 1 — Update the field types in `Settings`:
```python
from pydantic import SecretStr

postgres_password: SecretStr = SecretStr("change_me_locally")
portable_openai_api_key: SecretStr = SecretStr("")
azure_devops_pat: SecretStr = SecretStr("")
azure_search_api_key: SecretStr = SecretStr("")
```

Step 2 — Update every callsite that reads these fields to call `.get_secret_value()`:

| Field | Where it is consumed |
|---|---|
| `postgres_password` | `Settings.database_url` property (config.py ~line 77) |
| `azure_devops_pat` | `packages/integrations/azure_devops/client.py` (search for `settings.azure_devops_pat`) |
| `azure_search_api_key` | `packages/integrations/azure_search/client.py` |
| `portable_openai_api_key` | `packages/integrations/providers/portable/llm.py:11–16` — simplify the isinstance check once this is `SecretStr` |

Step 3 — After fixing `portable_openai_api_key` to `SecretStr`, simplify `portable/llm.py`:
```python
# BEFORE (lines 11–16)
raw_api_key = getattr(settings, "portable_openai_api_key", "")
api_key: SecretStr | None
if isinstance(raw_api_key, SecretStr):
    api_key = raw_api_key
elif isinstance(raw_api_key, str) and raw_api_key:
    api_key = SecretStr(raw_api_key)
else:
    api_key = None

# AFTER
raw = settings.portable_openai_api_key.get_secret_value()
api_key = SecretStr(raw) if raw else None
```

**Depends on:** Nothing — standalone change.
**Effort:** S (30 min)

---

### C2. No `.dockerignore` in any service directory

- [ ] **Status:** Open

**Problem:**
Every `docker build` context copies the entire project tree into the build layer unless
a `.dockerignore` exists. Without it, the following reach the image:
- `.env` files containing real credentials
- `.venv/` directory (hundreds of MB of dev packages)
- `tests/` and test fixtures
- `__pycache__` byte-code
- `node_modules/` (dashboard)
- `dist/` build artifacts

This inflates image size and, critically, risks baking a developer's `.env` secrets
into a published container image.

**Files to create (one per service):**

`apps/api/.dockerignore`:
```
.env
.env.*
.venv
__pycache__
*.pyc
*.pyo
*.pyd
.pytest_cache
.mypy_cache
.ruff_cache
tests/
htmlcov/
*.egg-info
dist/
build/
```

`apps/worker/.dockerignore`:
```
.env
.env.*
.venv
__pycache__
*.pyc
*.pyo
.pytest_cache
.mypy_cache
.ruff_cache
tests/
htmlcov/
*.egg-info
dist/
build/
```

`apps/dashboard/.dockerignore`:
```
node_modules/
dist/
.env
.env.*
*.log
coverage/
.vite/
```

`apps/docs/.dockerignore`:
```
node_modules/
build/
.env
.env.*
*.log
```

`apps/log_bridge/.dockerignore`:
```
.env
.env.*
__pycache__
*.pyc
.pytest_cache
tests/
```

**Depends on:** Nothing — standalone change.
**Effort:** S (20 min)

---

### C3. No authentication on API endpoints

- [ ] **Status:** Open

**Problem:**
Every FastAPI route — `/incidents`, `/metrics`, `/approvals`, `/integrations/health` —
is completely unauthenticated and publicly accessible. The only protection is
`target_api_token` for `/targets`, which is a static token. In production, any
client with network access to the API can read all incident data, trigger approvals,
and browse full stack traces.

**Files:**
- [`apps/api/main.py`](../apps/api/main.py) — no auth middleware registered
- [`apps/api/routers/incidents.py`](../apps/api/routers/incidents.py) — all routes unauthenticated
- [`apps/api/routers/approvals.py`](../apps/api/routers/approvals.py) — approval action unauthenticated
- [`apps/api/core/config.py`](../apps/api/core/config.py) — no auth settings defined

**Fix (minimum viable — static Bearer token, upgrade to Entra ID later):**

Step 1 — Add `api_bearer_token: SecretStr` to `Settings` (config.py):
```python
api_bearer_token: SecretStr = SecretStr("")  # required in production
```

Step 2 — Create `apps/api/core/auth.py`:
```python
from fastapi import Depends, HTTPException, Security, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from apps.api.core.config import get_settings

_bearer = HTTPBearer(auto_error=True)


def require_auth(
    credentials: HTTPAuthorizationCredentials = Security(_bearer),
) -> None:
    settings = get_settings()
    expected = settings.api_bearer_token.get_secret_value()
    if not expected:
        return  # auth disabled in local-dev when token is empty
    if credentials.credentials != expected:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing token",
        )
```

Step 3 — Apply the dependency to every router in `main.py`:
```python
from apps.api.core.auth import require_auth

app.include_router(incidents_router, dependencies=[Depends(require_auth)])
app.include_router(approvals_router, dependencies=[Depends(require_auth)])
app.include_router(metrics_router, dependencies=[Depends(require_auth)])
app.include_router(integrations_router, dependencies=[Depends(require_auth)])
app.include_router(targets_router, dependencies=[Depends(require_auth)])
```

Step 4 — Leave `/health` unauthenticated (liveness probes need it).

**Upgrade path (for AKS with Entra ID):**
Replace the token check in `require_auth` with Azure AD JWT validation using
`azure-identity` + `PyJWT`. The dependency signature stays the same; only the
validation logic inside changes.

**Depends on:** C1 (so the token is a `SecretStr`).
**Effort:** M (1–2 hours including tests)

---

### C4. OpenAPI docs (`/docs`, `/redoc`) publicly exposed in production

- [ ] **Status:** Open

**Problem:**
FastAPI enables `/docs` and `/redoc` by default in all environments. In production,
these pages document your entire API schema — all route paths, all request/response
shapes, all query parameters — without any authentication.

**Files:**
- [`apps/api/main.py`](../apps/api/main.py#L28) — `FastAPI(...)` constructor

**Fix:**

Step 1 — Gate the docs URLs on environment in `main.py`:
```python
_is_prod = settings.app_env == "production"

app = FastAPI(
    title="RemediAI API",
    version="0.1.0",
    description="AI-powered exception analysis and remediation platform",
    lifespan=lifespan,
    docs_url=None if _is_prod else "/docs",
    redoc_url=None if _is_prod else "/redoc",
    openapi_url=None if _is_prod else "/openapi.json",
)
```

**Depends on:** Nothing — standalone.
**Effort:** S (5 min)

---

### C5. `alembic.ini` has hardcoded database password committed to git

- [ ] **Status:** Open

**Problem:**
`alembic.ini` contains:
```ini
sqlalchemy.url = postgresql+asyncpg://remediai:change_me_locally@localhost:5432/remediai
```
While `alembic/env.py` overrides this with `DATABASE_URL`, the hardcoded fallback
stays in git history and is used if someone runs `alembic upgrade head` without
setting `DATABASE_URL`. More importantly, if a team member accidentally replaces
the placeholder with a real password, it gets committed.

**Files:**
- [`alembic.ini`](../alembic.ini) — `sqlalchemy.url` line
- [`alembic/env.py`](../alembic/env.py#L20) — `_default_url` variable

**Fix:**

Step 1 — Replace the `sqlalchemy.url` value in `alembic.ini` with a placeholder:
```ini
# Connection URL is resolved from DATABASE_URL env var at runtime (see alembic/env.py).
# Do NOT put real credentials here.
sqlalchemy.url = postgresql+asyncpg://placeholder:placeholder@localhost/placeholder
```

Step 2 — In `alembic/env.py`, enforce `DATABASE_URL` is set in non-local environments:
```python
import os

_env = os.environ.get("APP_ENV", "development")
_database_url = os.environ.get("DATABASE_URL", "")

if not _database_url:
    if _env == "production":
        raise RuntimeError("DATABASE_URL must be set in production")
    # local fallback only
    _database_url = "postgresql+asyncpg://remediai:change_me_locally@localhost:5432/remediai"

database_url: str = _database_url
```

Step 3 — Add `DATABASE_URL` to `.env.example` with instructions:
```env
# Set this to your full connection string. Used by Alembic migrations.
# Format: postgresql+asyncpg://user:password@host:port/dbname
DATABASE_URL=
```

**Depends on:** Nothing — standalone.
**Effort:** S (20 min)

---

## P1 — HIGH (next sprint)

Complete all P0 items before starting P1. Within P1, do H1 first — it is a
prerequisite for H2, H3, and unblocks M2 and M3.

---

### H1. Move `Settings` to a shared package — fixes 9 architecture violations

- [ ] **Status:** Open

**Problem:**
`packages/` (shared libraries, importable by any service) all import
`from apps.api.core.config import get_settings`. This is an inverted dependency:
shared libraries should never import from application-layer code. The violations are:

| File | Line | Type |
|---|---|---|
| `packages/data_access/session.py` | 5 | module-level import |
| `packages/agent_runtime/pipeline.py` | 49 | lazy import |
| `packages/agent_runtime/rag/agent.py` | 103 | lazy import in `_resolve_client` |
| `packages/agent_runtime/code_context/agent.py` | 113 | lazy import in `_resolve_client` |
| `packages/agent_runtime/bug_creator/agent.py` | 126 | lazy import in `_resolve_client` |
| `packages/agent_runtime/pr_agent/agent.py` | 231, 247 | lazy import (×2) |
| `packages/agent_runtime/validation_agent/agent.py` | 138, 154 | lazy import (×2) |

The worker app also imports `Settings` from the API app:

| File | Line |
|---|---|
| `apps/worker/main.py` | 14 |
| `apps/worker/ingestion/scheduler.py` | 8 |
| `apps/worker/agents/runner.py` | 11 |
| `apps/worker/agents/local_poller.py` | 18 |

**Fix:**

Step 1 — Create `packages/config/__init__.py` (empty) and
`packages/config/settings.py`:
```python
# packages/config/settings.py
from functools import lru_cache

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # (copy the full Settings body from apps/api/core/config.py verbatim)
    # The class is identical — only its location changes.
    ...


@lru_cache
def get_settings() -> Settings:
    return Settings()
```

Step 2 — Update `apps/api/core/config.py` to re-export from the new location
(keeps backwards compatibility for any imports you may have missed):
```python
# apps/api/core/config.py
from packages.config.settings import Settings, get_settings  # noqa: F401
```

Step 3 — Update all 11 import sites listed above to:
```python
from packages.config.settings import Settings, get_settings
```

Step 4 — Run `ruff check --fix` and `mypy --strict` to catch any missed callsites.

Step 5 — Delete the `Settings` class body from `apps/api/core/config.py`, leaving
only the re-export.

**Depends on:** C1 (SecretStr fields should be in place before copying the class).
**Effort:** M (1–2 hours)

---

### H2. Worker duplicates logging configuration

- [ ] **Status:** Open

**Problem:**
`apps/worker/main.py:19–32` implements its own `_configure_logging()` that is
different from `apps/api/core/logging.configure_logging()`. Specifically, it is
missing `StackInfoRenderer` and `ExceptionRenderer` processors. Exceptions logged
by the worker will not include stack traces in JSON output in production.

**Files:**
- [`apps/worker/main.py`](../apps/worker/main.py#L19) — `_configure_logging()` function

**Fix:**

Step 1 — Delete `_configure_logging()` from `apps/worker/main.py`.

Step 2 — Import the shared implementation. Note: `packages/observability/logging.py`
already has `configure_logging(app_env, log_level)`. Use that:
```python
# apps/worker/main.py
from packages.observability.logging import configure_logging

async def main() -> None:
    settings = get_settings()
    configure_logging(settings.app_env, settings.log_level)
    ...
```

**Depends on:** H1 (so worker imports settings from packages.config).
**Effort:** S (15 min)

---

### H3. Stub/test model in production integration module

- [ ] **Status:** Open

**Problem:**
`packages/integrations/providers/portable/llm.py` contains `create_stub_chat_model()`
with hardcoded JSON response strings. This is test fixture code that ships inside
the production `integrations` package and into production container images.

**Files:**
- [`packages/integrations/providers/portable/llm.py`](../packages/integrations/providers/portable/llm.py#L29) — lines 29–53
- Any callers (search for `create_stub_chat_model` across the codebase)

**Fix:**

Step 1 — Move the stub to `tests/fixtures/stub_llm.py`:
```python
# tests/fixtures/stub_llm.py
from langchain_core.language_models.fake_chat_models import FakeListChatModel
from langchain_core.language_models.chat_models import BaseChatModel

_TRIAGE_RESPONSE = '{"priority": "medium", ...}'
_ROOT_CAUSE_RESPONSE = '{"root_cause_summary": ...'
_FIX_PLANNER_RESPONSE = '{"recommendations": ...'


def create_stub_chat_model(_: object) -> BaseChatModel:
    responses = [
        _TRIAGE_RESPONSE, _ROOT_CAUSE_RESPONSE, _FIX_PLANNER_RESPONSE,
        _TRIAGE_RESPONSE, _ROOT_CAUSE_RESPONSE, _FIX_PLANNER_RESPONSE,
        _TRIAGE_RESPONSE, _ROOT_CAUSE_RESPONSE, _FIX_PLANNER_RESPONSE,
    ]
    return FakeListChatModel(responses=responses)
```

Step 2 — Update `tests/conftest.py` (or the integration test that uses the stub)
to import from `tests/fixtures/stub_llm.py` instead.

Step 3 — Delete lines 29–53 from `portable/llm.py`. Also remove the trailing
double blank line at line 28.

Step 4 — Verify `FakeListChatModel` import is removed from `portable/llm.py`
(it's a dev-only dependency; should not be required by production code).

**Depends on:** Nothing — standalone.
**Effort:** S (30 min)

---

### H4. No CORS middleware

- [ ] **Status:** Open

**Problem:**
The React dashboard calls `baseURL: '/api/v1'` which works when served from the
same origin via nginx proxy. But in local development, the dashboard runs on
`localhost:3000` and the API on `localhost:8000` — browsers will block all requests
due to CORS policy. There is no `CORSMiddleware` registered in `main.py`.

**Files:**
- [`apps/api/main.py`](../apps/api/main.py) — no CORS middleware
- [`apps/api/core/config.py`](../apps/api/core/config.py) — no `cors_origins` setting

**Fix:**

Step 1 — Add `cors_origins` to `Settings` (packages/config/settings.py after H1,
or apps/api/core/config.py now):
```python
cors_origins: str = "http://localhost:3000,http://localhost:8000"

@property
def cors_origins_list(self) -> list[str]:
    return [o.strip() for o in self.cors_origins.split(",") if o.strip()]
```

Step 2 — Register middleware in `apps/api/main.py` (add **before** the custom
correlation-ID middleware, as middleware executes in reverse order):
```python
from fastapi.middleware.cors import CORSMiddleware

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
    allow_headers=["*"],
)
```

Step 3 — Add `CORS_ORIGINS` to `.env.example`:
```env
# Comma-separated list of allowed CORS origins.
CORS_ORIGINS=http://localhost:3000
```

**Depends on:** Nothing — standalone.
**Effort:** S (20 min)

---

### H5. No rate limiting on API endpoints

- [ ] **Status:** Open

**Problem:**
There is no throttling on the FastAPI API. A single client (or a bug in the
dashboard's polling logic) can exhaust the PostgreSQL connection pool by issuing
thousands of requests per second to `/incidents` or `/metrics`.

**Files:**
- [`apps/api/main.py`](../apps/api/main.py) — no rate limiter configured
- [`pyproject.toml`](../pyproject.toml) — `slowapi` not in dependencies

**Fix (application-level via `slowapi`):**

Step 1 — Add dependency:
```toml
# pyproject.toml
slowapi = "^0.1"
```

Step 2 — Configure limiter in `apps/api/main.py`:
```python
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
```

Step 3 — Apply limits to high-traffic read routes:
```python
# apps/api/routers/incidents.py
from apps.api.main import limiter

@router.get("/incidents")
@limiter.limit("60/minute")
async def list_incidents(request: Request, ...):
    ...
```

**Alternative (preferred for AKS):** Configure rate limiting at the nginx Ingress
level in `infrastructure/helm/remediai/templates/dashboard/ingress.yaml` using
`nginx.ingress.kubernetes.io/limit-rps` annotations. This avoids adding a
dependency to the Python app and works transparently for all services.

**Depends on:** Nothing — standalone.
**Effort:** M (1–2 hours)

---

### H6. `apps/log_bridge/requirements.txt` isolated from `pyproject.toml`

- [ ] **Status:** Open

**Problem:**
The log bridge service has its own `requirements.txt` separate from the project's
`pyproject.toml`. This means:
1. `pip-audit` in the CI quality gate does not scan these dependencies for CVEs.
2. The log bridge can silently use a different version of a shared library
   (e.g., `requests`) than the rest of the project.
3. Running `poetry update` does not update log bridge dependencies.

**Files:**
- [`apps/log_bridge/requirements.txt`](../apps/log_bridge/requirements.txt) — standalone deps file
- [`pyproject.toml`](../pyproject.toml) — missing log bridge deps

**Fix:**

Step 1 — Read `apps/log_bridge/requirements.txt` to identify its dependencies.

Step 2 — Add them as a named dependency group in `pyproject.toml`:
```toml
[tool.poetry.group.log-bridge.dependencies]
# add whatever is in apps/log_bridge/requirements.txt here
```

Step 3 — Update `apps/log_bridge/Dockerfile` to install using the group:
```dockerfile
# Before:
RUN pip install -r requirements.txt

# After:
COPY pyproject.toml poetry.lock ./
RUN pip install poetry && poetry install --only log-bridge --no-root
```

Step 4 — Delete `apps/log_bridge/requirements.txt`.

Step 5 — Update the CI `quality-gate.yml` to ensure `pip-audit` covers this group.

**Depends on:** Nothing — standalone.
**Effort:** M (1 hour)

---

### H7. `/health` endpoint returns hardcoded version string

- [ ] **Status:** Open

**Problem:**
```python
return {"status": "ok", "version": "0.1.0", "env": settings.app_env}
```
The version is hardcoded. After every release, this remains `0.1.0` unless manually
updated, making it useless for production version tracking and Kubernetes readiness
checks.

**Files:**
- [`apps/api/main.py`](../apps/api/main.py#L60) — health endpoint

**Fix:**

Option A — Read from `pyproject.toml` at startup (zero config):
```python
from importlib.metadata import version, PackageNotFoundError

try:
    _APP_VERSION = version("remediai")
except PackageNotFoundError:
    _APP_VERSION = "dev"
```

Option B — Inject via Dockerfile build arg (best for containers):
```dockerfile
# apps/api/Dockerfile
ARG BUILD_VERSION=dev
ENV BUILD_VERSION=${BUILD_VERSION}
```
```python
# apps/api/core/config.py
build_version: str = "dev"   # populated by BUILD_VERSION env var
```
```python
# main.py
return {"status": "ok", "version": settings.build_version, "env": settings.app_env}
```

Update the CI release workflow (`release.yml`) to pass `--build-arg BUILD_VERSION=${{ github.ref_name }}` to `docker build`.

**Depends on:** Nothing — standalone.
**Effort:** S (20 min)

---

### H8. No graceful shutdown in the worker

- [ ] **Status:** Open

**Problem:**
The worker runs `asyncio.run(main())` with no signal handling. When Kubernetes
sends `SIGTERM` during a rolling update or scale-down event, the worker process
is killed immediately. If an agent pipeline is mid-run, the incident remains in
`triaging` status indefinitely — a stuck state that requires manual intervention.

**Files:**
- [`apps/worker/main.py`](../apps/worker/main.py#L35) — `main()` function and `asyncio.run()`
- [`apps/worker/ingestion/scheduler.py`](../apps/worker/ingestion/scheduler.py) — `run_forever()` loop
- [`apps/worker/agents/local_poller.py`](../apps/worker/agents/local_poller.py) — `run_forever()` loop

**Fix:**

Step 1 — Add a shutdown event to `main()`:
```python
import asyncio
import signal

async def main() -> None:
    settings = get_settings()
    configure_logging(settings.app_env, settings.log_level)
    logger = structlog.get_logger()

    shutdown_event = asyncio.Event()

    def _handle_sigterm() -> None:
        logger.info("worker_sigterm_received", note="draining current work")
        shutdown_event.set()

    loop = asyncio.get_running_loop()
    loop.add_signal_handler(signal.SIGTERM, _handle_sigterm)
    loop.add_signal_handler(signal.SIGINT, _handle_sigterm)

    if settings.local_mode:
        poller = LocalIncidentPoller(settings=settings, shutdown=shutdown_event)
        await poller.run_forever()
    else:
        scheduler = IngestionScheduler(settings=settings, shutdown=shutdown_event)
        await scheduler.run_forever()
```

Step 2 — Update `IngestionScheduler.run_forever()` and `LocalIncidentPoller.run_forever()`
to accept and poll the `shutdown_event`:
```python
async def run_forever(self) -> None:
    while not self._shutdown.is_set():
        await self._poll_once()
        try:
            await asyncio.wait_for(
                self._shutdown.wait(),
                timeout=self._poll_interval_seconds,
            )
        except asyncio.TimeoutError:
            pass
    self._log.info("worker_shutdown_clean")
```

Step 3 — Add `terminationGracePeriodSeconds: 60` to the worker Helm deployment
template (`infrastructure/helm/remediai/templates/worker-agents/deployment.yaml`)
so Kubernetes waits long enough for the drain.

**Depends on:** H1 (settings import), H2 (logging).
**Effort:** M (1–3 hours)

---

### H9. `axios` client has no timeout, no global error interceptors

- [ ] **Status:** Open

**Problem:**
`apps/dashboard/src/api/client.ts` creates an axios instance with only `baseURL`
and `Content-Type`. There is no:
- **Request timeout** — a hung API call will wait forever, freezing the UI.
- **Error interceptor** — 401, 5xx responses silently fail with no user feedback.
- **Correlation ID forwarding** — the backend's `X-Correlation-ID` middleware
  requires the header to be sent, but the frontend never sends it.

**Files:**
- [`apps/dashboard/src/api/client.ts`](../apps/dashboard/src/api/client.ts)

**Fix:**
```typescript
// apps/dashboard/src/api/client.ts
import axios from 'axios'
import { v4 as uuidv4 } from 'uuid'  // add uuid to package.json if not present

const client = axios.create({
  baseURL: '/api/v1',
  headers: { 'Content-Type': 'application/json' },
  timeout: 30_000,
})

// Attach a correlation ID to every request for backend tracing
client.interceptors.request.use((config) => {
  config.headers['X-Correlation-ID'] = uuidv4()
  return config
})

// Global error handling
client.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      // Redirect to login or show auth error
      window.location.href = '/login'
    }
    // Re-throw so individual query hooks can also handle the error
    return Promise.reject(error)
  },
)

export default client
```

If you prefer not to add `uuid`, use `crypto.randomUUID()` (available in all
modern browsers and Node 19+):
```typescript
config.headers['X-Correlation-ID'] = crypto.randomUUID()
```

**Depends on:** Nothing — standalone.
**Effort:** S (30 min)

---

### H10. No React `ErrorBoundary`

- [ ] **Status:** Open

**Problem:**
If any page component throws an unhandled JavaScript error (e.g., a `null`
dereference on unexpected API data shape), React 18 unmounts the entire component
tree and renders a blank white page. There is no error boundary to catch render
errors and show a meaningful fallback.

**Files:**
- [`apps/dashboard/src/App.tsx`](../apps/dashboard/src/App.tsx)

**Fix:**

Step 1 — Install `react-error-boundary`:
```bash
npm install react-error-boundary
```

Step 2 — Create `apps/dashboard/src/components/AppErrorFallback.tsx`:
```tsx
interface Props {
  error: Error
  resetErrorBoundary: () => void
}

export function AppErrorFallback({ error, resetErrorBoundary }: Props) {
  return (
    <div className="flex flex-col items-center justify-center min-h-screen p-8">
      <h1 className="text-2xl font-bold text-red-600 mb-4">Something went wrong</h1>
      <pre className="text-sm text-gray-700 bg-gray-100 rounded p-4 max-w-lg overflow-auto mb-6">
        {error.message}
      </pre>
      <button
        onClick={resetErrorBoundary}
        className="px-4 py-2 bg-blue-600 text-white rounded hover:bg-blue-700"
      >
        Try again
      </button>
    </div>
  )
}
```

Step 3 — Wrap routes in `App.tsx`:
```tsx
import { ErrorBoundary } from 'react-error-boundary'
import { AppErrorFallback } from './components/AppErrorFallback'

export function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <ErrorBoundary FallbackComponent={AppErrorFallback}>
          <Routes>
            {/* existing routes */}
          </Routes>
        </ErrorBoundary>
      </BrowserRouter>
    </QueryClientProvider>
  )
}
```

**Depends on:** Nothing — standalone.
**Effort:** S (30 min)

---

### H11. No 404 catch-all route in the React app

- [ ] **Status:** Open

**Problem:**
Navigating to any unknown URL path renders a blank page with no feedback.
The user has no way to tell whether the app is broken or the URL is invalid.

**Files:**
- [`apps/dashboard/src/App.tsx`](../apps/dashboard/src/App.tsx)

**Fix:**

Step 1 — Create `apps/dashboard/src/pages/NotFound.tsx`:
```tsx
import { Link } from 'react-router-dom'

export function NotFound() {
  return (
    <div className="flex flex-col items-center justify-center py-24">
      <h1 className="text-4xl font-bold text-gray-900 mb-2">404</h1>
      <p className="text-gray-500 mb-6">Page not found.</p>
      <Link to="/incidents" className="text-blue-600 hover:underline">
        Back to Incidents
      </Link>
    </div>
  )
}
```

Step 2 — Add as the last route in `App.tsx`:
```tsx
import { NotFound } from './pages/NotFound'

<Route path="*" element={<NotFound />} />
```

**Depends on:** Nothing — standalone.
**Effort:** S (15 min)

---

## P2 — MEDIUM (code quality / technical debt)

These items do not block production but create maintenance burden. Tackle after
all P0 and P1 items.

---

### M1. LLM JSON parsing boilerplate duplicated across 5 agent files

- [ ] **Status:** Open

**Problem:**
The pattern of extracting JSON from an LLM text response (splitting on ` ```json `,
`json.loads`, error fallback) is copy-pasted into at least 5 agent files:
`triage/agent.py`, `root_cause/agent.py`, `fix_planner/agent.py`,
`pr_agent/agent.py`, `validation_agent/agent.py`.
A bug in the parsing logic must be fixed in 5 places.

**Fix:**
Create `packages/agent_runtime/utils.py`:
```python
from __future__ import annotations

import json
import re
from typing import Any


def parse_llm_json_response(content: str) -> dict[str, Any]:
    """Extract and parse a JSON object from an LLM text response.

    Handles responses that may be:
    - Raw JSON
    - JSON wrapped in a markdown ```json ... ``` code block
    - JSON wrapped in a plain ``` ... ``` code block
    """
    text = content.strip()

    # Try to extract from markdown code block first
    match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
    if match:
        text = match.group(1)

    try:
        result = json.loads(text)
        if isinstance(result, dict):
            return result
    except json.JSONDecodeError:
        pass

    # Last resort: find the first { ... } block
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if match:
        try:
            result = json.loads(match.group(0))
            if isinstance(result, dict):
                return result
        except json.JSONDecodeError:
            pass

    return {}
```

Replace the inline parsing in all 5 agent files with:
```python
from packages.agent_runtime.utils import parse_llm_json_response

parsed = parse_llm_json_response(response.content)
```

**Depends on:** Nothing — standalone.
**Effort:** M (1–2 hours)

---

### M2. `AgentTraceEntry` latency measurement boilerplate in every agent

- [ ] **Status:** Open

**Problem:**
Every agent node contains identical boilerplate:
```python
start_ms = int(time.monotonic() * 1000)
# ... agent work ...
latency_ms = int(time.monotonic() * 1000) - start_ms
trace_entry = AgentTraceEntry(
    agent_name=AGENT_NAME, ..., latency_ms=latency_ms, error=error
)
```
This pattern appears 7+ times across the agent runtime.

**Fix:**
Add an async context manager to `packages/agent_runtime/utils.py`:
```python
import time
from contextlib import asynccontextmanager
from collections.abc import AsyncGenerator
from packages.domain.models.audit import AgentTraceEntry


@asynccontextmanager
async def agent_trace(
    agent_name: str,
    input_summary: str,
    prompt_version: str | None = None,
) -> AsyncGenerator[dict[str, Any], None]:
    start_ms = int(time.monotonic() * 1000)
    ctx: dict[str, Any] = {"error": None}
    try:
        yield ctx
    except Exception as exc:
        ctx["error"] = str(exc)
        raise
    finally:
        latency_ms = int(time.monotonic() * 1000) - start_ms
        ctx["trace_entry"] = AgentTraceEntry(
            agent_name=agent_name,
            prompt_version=prompt_version,
            input_summary=input_summary,
            output_summary=ctx.get("output_summary", ""),
            latency_ms=latency_ms,
            error=ctx["error"],
        ).model_dump()
```

Usage in an agent:
```python
async with agent_trace(AGENT_NAME, input_summary=f"incident={incident_id}") as ctx:
    ctx["output_summary"] = f"labels={labels}"
    # ... agent work ...

trace_entry = ctx["trace_entry"]
```

**Depends on:** M1 (same file — create utils.py once).
**Effort:** M (2 hours — context manager + refactor all agents)

---

### M3. `build_pipeline()` and agent factories typed as `Any`

- [ ] **Status:** Open

**Problem:**
`packages/agent_runtime/pipeline.py` accepts `settings: Any`, `llm: Any`, and
client parameters typed as `Any`. This defeats mypy's strict checking for the
entire pipeline construction path.

**Files:**
- `packages/agent_runtime/pipeline.py` — function signatures

**Fix:**
Add a `PipelineClients` TypedDict to `packages/agent_runtime/pipeline.py` (or a
new `packages/agent_runtime/types.py`):
```python
from typing import TypedDict

from packages.config.settings import Settings

class PipelineClients(TypedDict, total=False):
    search_client: SearchClientProtocol | None
    ado_client: AdoClientProtocol | None
    repos_writer: ReposWriterProtocol | None
    pr_reader: PrReaderProtocol | None


def build_pipeline(
    settings: Settings,
    llm: BaseChatModel,
    clients: PipelineClients | None = None,
) -> CompiledGraph:
    ...
```

**Depends on:** H1 (shared Settings type).
**Effort:** M (2 hours)

---

### M4. `call_next: object` wrong type in FastAPI middleware

- [ ] **Status:** Open

**Problem:**
`apps/api/main.py:37` uses `object` as the type for `call_next`, which suppresses
type checking for the middleware. The `# type: ignore[operator]` on the next line
is a symptom.

**Files:**
- [`apps/api/main.py`](../apps/api/main.py#L37)

**Fix:**
```python
from collections.abc import Awaitable, Callable

@app.middleware("http")
async def correlation_id_middleware(
    request: Request,
    call_next: Callable[[Request], Awaitable[Response]],
) -> Response:
    correlation_id = request.headers.get(settings.correlation_id_header, "")
    structlog.contextvars.bind_contextvars(correlation_id=correlation_id)
    response = await call_next(request)   # type: ignore removed
    if correlation_id:
        response.headers[settings.correlation_id_header] = correlation_id
    structlog.contextvars.clear_contextvars()
    return response
```

**Depends on:** Nothing — standalone.
**Effort:** S (5 min)

---

### M5. `_resolve_client()` pattern duplicated across 6 agent files

- [ ] **Status:** Open

**Problem:**
Each agent has its own `_resolve_client(provided, settings)` or
`_resolve_*_client(...)` function that lazily instantiates the integration client
from settings if not provided. The pattern is nearly identical across
`rag/agent.py`, `code_context/agent.py`, `bug_creator/agent.py`,
`pr_agent/agent.py`, `validation_agent/agent.py`.

**Fix:**
Add to `packages/agent_runtime/utils.py`:
```python
from collections.abc import Callable
from typing import TypeVar

T = TypeVar("T")


def resolve_client(
    provided: T | None,
    factory: Callable[[], T | None],
) -> T | None:
    """Return `provided` if set, otherwise call `factory()` to build from settings."""
    if provided is not None:
        return provided
    return factory()
```

Usage:
```python
client = resolve_client(
    search_client,
    lambda: AzureSearchClient.from_settings(settings or get_settings())
    if (settings or get_settings()).azure_search_endpoint
    else None,
)
```

**Depends on:** M1 (same utils.py file).
**Effort:** M (1–2 hours — add utility + refactor 6 agent files)

---

## P3 — LOW (cleanup)

These items reduce clutter and maintenance overhead. Schedule as a dedicated
"housekeeping" phase.

---

### L1. Delete empty placeholder files in `infrastructure/`

- [ ] **Status:** Open

**Problem:**
Three directories contain only a `.gitkeep` with no actual content:
- `infrastructure/terraform/.gitkeep` — Phase 23 (IaC) not started
- `infrastructure/k8s/.gitkeep` — no raw k8s manifests exist yet
- `infrastructure/helm/.gitkeep` — parent of the actual Helm charts

The Terraform and k8s directories imply content that does not exist, misleading
contributors.

**Fix:**
```bash
# Remove empty placeholder directories until Phase 23 begins
rm infrastructure/terraform/.gitkeep
rmdir infrastructure/terraform  # only if empty

rm infrastructure/k8s/.gitkeep
rmdir infrastructure/k8s  # only if empty

rm infrastructure/helm/.gitkeep  # parent .gitkeep is redundant; charts exist in helm/remediai/
```

When Phase 23 begins, recreate `infrastructure/terraform/` with an actual
`main.tf` stub and `README.md`.

**Depends on:** Nothing.
**Effort:** S (5 min)

---

### L2. Commit or delete untracked `docs/configuration-management.md`

- [ ] **Status:** Open

**Problem:**
`docs/configuration-management.md` shows as `??` (untracked) in `git status`. It
is either a draft that should be committed or a stale file that should be deleted.
Leaving it untracked means it will not appear in CI, code review, or the Docusaurus
docs site build.

**Fix:**
- If the document is complete and accurate → `git add docs/configuration-management.md`
  and commit it in the next phase commit.
- If it is a draft → move to a local notes folder outside the repo, or delete it.
- Add it to the Docusaurus sidebar if it should appear in the public docs site.

**Depends on:** Nothing.
**Effort:** S (10 min)

---

### L3. Archive superseded prompt versions

- [ ] **Status:** Open

**Problem:**
`docs/prompts/triage_v1.md` and `docs/prompts/root_cause_v1.md` are superseded
by their v2 counterparts. Keeping both creates confusion about which prompt is
active and makes `scripts/validate_prompt_contracts.py` validate stale contracts.

**Fix:**
Confirm v2 is active in production (check `packages/agent_runtime/prompt_registry.py`
for which version is loaded). Then:
```bash
mkdir -p docs/prompts/archive
git mv docs/prompts/triage_v1.md docs/prompts/archive/
git mv docs/prompts/root_cause_v1.md docs/prompts/archive/
```

Update `scripts/validate_prompt_contracts.py` to skip the `archive/` subdirectory.

**Depends on:** Nothing.
**Effort:** S (15 min)

---

### L4. Decide on `.copilot-instructions.md`

- [ ] **Status:** Open

**Problem:**
`.copilot-instructions.md` (204 lines) largely duplicates `CLAUDE.md`. Maintaining
two AI-assistant instruction files creates drift — a rule update in `CLAUDE.md`
must also be applied to `.copilot-instructions.md` or they diverge.

**Fix:**
- If the team uses GitHub Copilot → keep the file, but add a comment at the top
  pointing to `CLAUDE.md` as the canonical source and schedule periodic sync.
- If no one uses Copilot → `git rm .copilot-instructions.md`.

**Depends on:** Nothing.
**Effort:** S (10 min decision + cleanup)

---

## Dependency Map

The diagram below shows which items must be done before others. Complete items
in topological order within each priority tier.

```
C1 (SecretStr)
  └─► C3 (API auth)
  └─► H1 (shared config)
        ├─► H2 (worker logging)
        ├─► H8 (graceful shutdown)
        └─► M3 (pipeline types)

H1 (shared config)  ← independent prerequisite for most P1+P2 items

M1 (utils.py: parse_llm_json)
  └─► M2 (utils.py: agent_trace)
  └─► M5 (utils.py: resolve_client)

H3 (stub model → tests)  ← standalone, no deps
H4 (CORS)                ← standalone, no deps
H5 (rate limiting)       ← standalone, no deps
H6 (log_bridge deps)     ← standalone, no deps
H7 (health version)      ← standalone, no deps
H9 (axios interceptors)  ← standalone, no deps
H10 (ErrorBoundary)      ← standalone, no deps
H11 (NotFound route)     ← standalone, no deps
```

---

## Completion Checklist (all items)

```
P0 — CRITICAL
  [ ] C1  SecretStr for postgres_password, azure_devops_pat, azure_search_api_key, portable_openai_api_key
  [ ] C2  Add .dockerignore to api, worker, dashboard, docs, log_bridge
  [ ] C3  Add Bearer token auth middleware to all FastAPI routers
  [ ] C4  Disable /docs and /redoc in production (app_env=production)
  [ ] C5  Remove hardcoded password from alembic.ini; guard DATABASE_URL in env.py

P1 — HIGH
  [ ] H1  Move Settings/get_settings to packages/config/settings.py
  [ ] H2  Worker uses packages/observability/logging.configure_logging
  [ ] H3  Move create_stub_chat_model to tests/fixtures/
  [ ] H4  Add CORSMiddleware with cors_origins setting
  [ ] H5  Add rate limiting (slowapi or nginx ingress)
  [ ] H6  Consolidate log_bridge requirements into pyproject.toml
  [ ] H7  Dynamic version in /health endpoint
  [ ] H8  SIGTERM graceful shutdown in worker
  [ ] H9  axios timeout + error interceptors + correlation ID header
  [ ] H10 Wrap routes in ErrorBoundary (react-error-boundary)
  [ ] H11 Add <Route path="*"> 404 NotFound handler

P2 — MEDIUM
  [ ] M1  Extract parse_llm_json_response() to packages/agent_runtime/utils.py
  [ ] M2  Extract agent_trace() context manager to packages/agent_runtime/utils.py
  [ ] M3  Type build_pipeline() with Settings + PipelineClients TypedDict
  [ ] M4  Fix call_next type annotation in correlation_id_middleware
  [ ] M5  Extract resolve_client() to packages/agent_runtime/utils.py

P3 — LOW
  [ ] L1  Delete infrastructure/terraform/.gitkeep and infrastructure/k8s/.gitkeep
  [ ] L2  Commit or delete docs/configuration-management.md
  [ ] L3  Archive superseded prompt versions (triage_v1.md, root_cause_v1.md)
  [ ] L4  Decide on .copilot-instructions.md — keep or remove
```

---

*This document was generated from a full architectural review on 2026-05-25.
Each fix is scoped to match the problem described — no additional refactoring
beyond what is specified.*
