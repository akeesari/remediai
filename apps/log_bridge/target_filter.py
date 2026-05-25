"""Target allowlist loading and matching for the local log bridge."""

from __future__ import annotations

from typing import Any

import httpx
import structlog

logger = structlog.get_logger()


class TargetFilter:
    def __init__(self, *, api_url: str, client: httpx.Client) -> None:
        self._api_url = api_url.rstrip("/")
        self._client = client
        self._enabled_containers: set[str] = set()

    @property
    def enabled_containers(self) -> set[str]:
        return set(self._enabled_containers)

    def refresh(self) -> None:
        try:
            resp = self._client.get(
                f"{self._api_url}/api/v1/targets",
                params={"environment": "local", "enabled_only": True},
            )
            resp.raise_for_status()
            payload: list[dict[str, Any]] = resp.json()
            self._enabled_containers = {
                str(item.get("target_key", "")).strip()
                for item in payload
                if str(item.get("target_type", "")).strip() == "container"
                and str(item.get("target_key", "")).strip()
            }
            logger.info("bridge_targets_refreshed", enabled_count=len(self._enabled_containers))
        except Exception as exc:
            logger.warning("bridge_targets_refresh_failed", error=str(exc))

    def is_enabled(self, container: str) -> bool:
        return container in self._enabled_containers
