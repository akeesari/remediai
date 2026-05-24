"""Worker process entry-point.

Run with:
    poetry run python -m apps.worker.main
"""

from __future__ import annotations

import asyncio
import logging

import structlog

from apps.api.core.config import get_settings
from apps.worker.ingestion.scheduler import IngestionScheduler


def _configure_logging(log_level: str) -> None:
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.stdlib.add_log_level,
            structlog.stdlib.add_logger_name,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(
            logging.getLevelName(log_level.upper())
        ),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(),
    )


async def main() -> None:
    settings = get_settings()
    _configure_logging(settings.log_level)

    logger = structlog.get_logger()
    logger.info(
        "worker_starting",
        env=settings.app_env,
        poll_interval=settings.ingestion_poll_interval_seconds,
    )

    scheduler = IngestionScheduler(settings=settings)
    await scheduler.run_forever()


if __name__ == "__main__":
    asyncio.run(main())
