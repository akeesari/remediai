"""Worker process entry-point.

Run with:
    poetry run python -m apps.worker.main
"""

from __future__ import annotations

import asyncio

import structlog

from apps.worker.agents.local_poller import LocalIncidentPoller
from apps.worker.ingestion.scheduler import IngestionScheduler
from packages.config.settings import get_settings
from packages.observability.logging import configure_logging


async def main() -> None:
    settings = get_settings()
    configure_logging("worker", settings.log_level)

    logger = structlog.get_logger()
    logger.info(
        "worker_starting",
        env=settings.app_env,
        poll_interval=settings.ingestion_poll_interval_seconds,
    )

    if settings.local_mode:
        logger.info("worker_local_mode", note="using LocalIncidentPoller instead of Azure Monitor")
        poller = LocalIncidentPoller(settings=settings)
        await poller.run_forever()
    else:
        scheduler = IngestionScheduler(settings=settings)
        await scheduler.run_forever()


if __name__ == "__main__":
    asyncio.run(main())
