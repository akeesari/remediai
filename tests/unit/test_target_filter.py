from __future__ import annotations

from unittest.mock import MagicMock

from apps.log_bridge.target_filter import TargetFilter


def test_refresh_loads_enabled_container_targets() -> None:
    client = MagicMock()
    response = MagicMock()
    response.json.return_value = [
        {"target_type": "container", "target_key": "api"},
        {"target_type": "container", "target_key": "worker"},
        {"target_type": "namespace", "target_key": "default"},
    ]
    client.get.return_value = response

    target_filter = TargetFilter(api_url="http://api:8000", client=client)
    target_filter.refresh()

    assert target_filter.enabled_containers == {"api", "worker"}
    assert target_filter.is_enabled("api") is True
    assert target_filter.is_enabled("dashboard") is False


def test_refresh_failure_keeps_previous_allowlist() -> None:
    client = MagicMock()
    ok_response = MagicMock()
    ok_response.json.return_value = [{"target_type": "container", "target_key": "api"}]
    client.get.return_value = ok_response

    target_filter = TargetFilter(api_url="http://api:8000", client=client)
    target_filter.refresh()
    assert target_filter.enabled_containers == {"api"}

    client.get.side_effect = RuntimeError("network")
    target_filter.refresh()

    assert target_filter.enabled_containers == {"api"}
