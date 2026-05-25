"""Tails Docker container logs and yields (container_name, line) pairs."""

from __future__ import annotations

import threading
import time
from collections.abc import Callable

import docker
import docker.errors
import structlog

logger = structlog.get_logger()


class ContainerLogTailer:
    """Spawns a background thread that streams logs from one Docker container."""

    def __init__(
        self,
        service_name: str,
        compose_project: str,
        on_line: Callable[[str, str], None],
        since_seconds: int = 60,
    ) -> None:
        self._service = service_name
        self._project = compose_project
        self._on_line = on_line
        self._since = since_seconds
        self._stop = threading.Event()

    def start(self) -> None:
        t = threading.Thread(target=self._run, daemon=True, name=f"tailer-{self._service}")
        t.start()

    def stop(self) -> None:
        self._stop.set()

    def _run(self) -> None:
        log = logger.bind(service=self._service, project=self._project)
        client = docker.from_env()

        while not self._stop.is_set():
            try:
                containers = client.containers.list(
                    filters={
                        "label": [
                            f"com.docker.compose.service={self._service}",
                            f"com.docker.compose.project={self._project}",
                        ]
                    }
                )
                if not containers:
                    log.warning("tailer_container_not_found")
                    time.sleep(10)
                    continue

                container = containers[0]
                log.info("tailer_started", container_id=container.short_id)

                stream = container.logs(
                    stream=True,
                    follow=True,
                    since=self._since,
                    timestamps=False,
                )
                for chunk in stream:
                    if self._stop.is_set():
                        break
                    for raw_line in chunk.decode("utf-8", errors="replace").splitlines():
                        line = raw_line.strip()
                        if line:
                            self._on_line(self._service, line)

                log.warning("tailer_stream_ended")

            except docker.errors.NotFound:
                log.warning("tailer_container_removed")
            except Exception as exc:
                log.error("tailer_error", error=str(exc))

            if not self._stop.is_set():
                time.sleep(5)
