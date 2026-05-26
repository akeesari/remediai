from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

import structlog.contextvars
from fastapi import Depends, FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware

from apps.api.core.auth import require_auth
from apps.api.core.config import get_settings
from apps.api.core.logging import configure_logging, get_logger
from apps.api.routers.approvals import router as approvals_router
from apps.api.routers.incidents import router as incidents_router
from apps.api.routers.integrations import router as integrations_router
from apps.api.routers.local_logs import router as local_logs_router
from apps.api.routers.metrics import router as metrics_router
from apps.api.routers.targets import router as targets_router

settings = get_settings()
configure_logging(settings.app_env, settings.log_level)
logger = get_logger(__name__)

_CORRELATION_ID_HEADER = "X-Correlation-ID"
_prod = settings.app_env == "production"


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    logger.info("remediai_api_starting", env=settings.app_env, log_level=settings.log_level)
    yield
    logger.info("remediai_api_stopped")


app = FastAPI(
    title="RemediAI API",
    version="0.1.0",
    description="AI-powered exception analysis and remediation platform",
    lifespan=lifespan,
    docs_url=None if _prod else "/docs",
    redoc_url=None if _prod else "/redoc",
    openapi_url=None if _prod else "/openapi.json",
)


_cors_origins = [o.strip() for o in settings.cors_origins.split(",") if o.strip()]
if _cors_origins:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=_cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )


@app.middleware("http")
async def correlation_id_middleware(request: Request, call_next: object) -> Response:
    correlation_id = request.headers.get(_CORRELATION_ID_HEADER, "")
    structlog.contextvars.bind_contextvars(correlation_id=correlation_id)
    response: Response = await call_next(request)  # type: ignore[operator]
    if correlation_id:
        response.headers[_CORRELATION_ID_HEADER] = correlation_id
    structlog.contextvars.clear_contextvars()
    return response


_auth = [Depends(require_auth)]

app.include_router(incidents_router, dependencies=_auth)
app.include_router(approvals_router, dependencies=_auth)
app.include_router(metrics_router, dependencies=_auth)
app.include_router(integrations_router, dependencies=_auth)
app.include_router(targets_router, dependencies=_auth)

if settings.local_mode:
    app.include_router(local_logs_router, dependencies=_auth)
    logger.info("local_mode_enabled", endpoints=["/api/v1/local/ingest", "/api/v1/local/logs"])


@app.get("/health", tags=["system"])
async def health() -> dict[str, str]:
    return {"status": "ok", "version": "0.1.0", "env": settings.app_env}
