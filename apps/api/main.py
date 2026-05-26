from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

import structlog.contextvars
from fastapi import FastAPI, Request, Response

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


app.include_router(incidents_router)
app.include_router(approvals_router)
app.include_router(metrics_router)
app.include_router(integrations_router)
app.include_router(targets_router)

if settings.local_mode:
    app.include_router(local_logs_router)
    logger.info("local_mode_enabled", endpoints=["/api/v1/local/ingest", "/api/v1/local/logs"])


@app.get("/health", tags=["system"])
async def health() -> dict[str, str]:
    return {"status": "ok", "version": "0.1.0", "env": settings.app_env}
