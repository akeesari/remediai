from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

import structlog.contextvars
from fastapi import FastAPI, Request, Response

from apps.api.core.config import get_settings
from apps.api.core.logging import configure_logging, get_logger

settings = get_settings()
configure_logging(settings.app_env, settings.log_level)
logger = get_logger(__name__)


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
    correlation_id = request.headers.get(settings.correlation_id_header, "")
    structlog.contextvars.bind_contextvars(correlation_id=correlation_id)
    response: Response = await call_next(request)  # type: ignore[operator]
    if correlation_id:
        response.headers[settings.correlation_id_header] = correlation_id
    structlog.contextvars.clear_contextvars()
    return response


@app.get("/health", tags=["system"])
async def health() -> dict[str, str]:
    return {"status": "ok", "version": "0.1.0", "env": settings.app_env}
