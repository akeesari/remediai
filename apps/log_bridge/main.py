"""Local Log Bridge entry point.

Tails Docker container stdout for the configured services, detects Python
exceptions, stores all log lines in Redis, and POSTs exceptions to the API
so they enter the normal incident → agent pipeline flow.
"""

from __future__ import annotations

import json
import logging
import os
import signal
import time
from datetime import UTC, datetime

import httpx
import redis
import structlog

from apps.log_bridge.exception_parser import ExceptionParser
from apps.log_bridge.log_tailer import ContainerLogTailer

structlog.configure(
    processors=[
        structlog.stdlib.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.JSONRenderer(),
    ],
    wrapper_class=structlog.make_filtering_bound_logger(logging.INFO),
    logger_factory=structlog.PrintLoggerFactory(),
)

logger = structlog.get_logger()

_REDIS_LOG_KEY = "local:logs"
_REDIS_MAX_LINES = 1000
_LEVEL_KEYWORDS = {"ERROR", "CRITICAL", "WARNING", "WARN"}


def _detect_level(line: str) -> str:
    upper = line.upper()
    for kw in _LEVEL_KEYWORDS:
        if kw in upper:
            return kw
    return "INFO"


class Bridge:
    def __init__(self) -> None:
        self._api_url = os.environ.get("API_URL", "http://api:8000")
        self._redis_url = os.environ.get("REDIS_URL", "redis://redis:6379/0")
        self._project = os.environ.get("COMPOSE_PROJECT_NAME", "remediai")
        self._services = [
            s.strip()
            for s in os.environ.get("BRIDGE_CONTAINERS", "api,worker,dashboard").split(",")
            if s.strip()
        ]
        self._redis: redis.Redis = redis.from_url(self._redis_url)  # type: ignore[no-untyped-call]
        self._parsers: dict[str, ExceptionParser] = {s: ExceptionParser() for s in self._services}
        self._http = httpx.Client(timeout=10)
        self._tailers: list[ContainerLogTailer] = []

    def _handle_line(self, service: str, line: str) -> None:
        level = _detect_level(line)
        entry: dict[str, object] = {
            "ts": datetime.now(UTC).isoformat(),
            "container": service,
            "line": line,
            "level": level,
            "is_exception": False,
            "incident_id": None,
        }

        exc = self._parsers[service].feed(line)
        if exc:
            incident_id = self._ingest_exception(
                service, exc.exception_type, exc.exception_message, exc.stack_trace
            )
            entry["is_exception"] = True
            entry["incident_id"] = incident_id
            entry["level"] = "ERROR"

        self._redis.lpush(_REDIS_LOG_KEY, json.dumps(entry))
        self._redis.ltrim(_REDIS_LOG_KEY, 0, _REDIS_MAX_LINES - 1)

    def _ingest_exception(
        self,
        container: str,
        exc_type: str,
        exc_msg: str,
        stack_trace: str,
    ) -> str | None:
        log = logger.bind(container=container, exception_type=exc_type)
        try:
            resp = self._http.post(
                f"{self._api_url}/api/v1/local/ingest",
                json={
                    "container": container,
                    "exception_type": exc_type,
                    "exception_message": exc_msg,
                    "stack_trace": stack_trace,
                    "source": "local-docker",
                },
            )
            resp.raise_for_status()
            data: dict[str, object] = resp.json()
            incident_id = data.get("incident_id")
            log.info("bridge_ingest_ok", status=data.get("status"), incident_id=incident_id)
            return str(incident_id) if incident_id else None
        except Exception as err:
            log.error("bridge_ingest_failed", error=str(err))
            return None

    def run(self) -> None:
        logger.info("bridge_starting", services=self._services, project=self._project)

        for service in self._services:
            tailer = ContainerLogTailer(
                service_name=service,
                compose_project=self._project,
                on_line=self._handle_line,
            )
            tailer.start()
            self._tailers.append(tailer)

        def _shutdown(sig: int, _frame: object) -> None:
            logger.info("bridge_shutdown", signal=sig)
            for t in self._tailers:
                t.stop()

        signal.signal(signal.SIGTERM, _shutdown)
        signal.signal(signal.SIGINT, _shutdown)

        logger.info("bridge_running")
        while True:
            time.sleep(60)


if __name__ == "__main__":
    Bridge().run()
