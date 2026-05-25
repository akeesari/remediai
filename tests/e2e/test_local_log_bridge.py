"""Live stack end-to-end tests for the local log bridge.

These tests exercise the FULL pipeline against a running local Docker stack:

    dev/throw endpoint
        → uvicorn logs exception to stderr
        → log-bridge container detects the traceback
        → log-bridge POSTs to /api/v1/local/ingest
        → incident row created in Postgres
        → /api/v1/local/logs returns the exception log line
        → LocalIncidentPoller picks up the incident (if AZURE_OPENAI_ENDPOINT set)
        → incident status transitions from new → analyzed

Prerequisites (must be satisfied before running):
    make local-up          # starts all 6 containers
    make local-migrate     # applies Alembic migrations

Run with:
    make local-bridge-e2e

Or directly:
    pytest tests/e2e/test_local_log_bridge.py -v -m local_bridge

Environment:
    LOCAL_API_URL       override API base URL (default: http://localhost:8000)
    BRIDGE_POLL_TIMEOUT override max wait for bridge detection (default: 45s)
    PIPELINE_TIMEOUT    override max wait for pipeline completion (default: 120s)
"""

from __future__ import annotations

import os
import time
import uuid

import httpx
import pytest

_API_BASE = os.environ.get("LOCAL_API_URL", "http://localhost:8000")
_BRIDGE_TIMEOUT = int(os.environ.get("BRIDGE_POLL_TIMEOUT", "45"))
_PIPELINE_TIMEOUT = int(os.environ.get("PIPELINE_TIMEOUT", "120"))
_POLL_INTERVAL = 2  # seconds between polls


pytestmark = pytest.mark.local_bridge


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _api(path: str, **kwargs: object) -> str:
    return f"{_API_BASE}{path}"


def _check_prerequisites(client: httpx.Client) -> None:
    """Fail fast with a useful message if the stack is not running."""
    try:
        health = client.get(_api("/health"), timeout=5)
        health.raise_for_status()
    except Exception as exc:
        pytest.skip(f"Local stack not running at {_API_BASE} — run `make local-up` first. ({exc})")

    try:
        logs = client.get(_api("/api/v1/local/logs"), params={"limit": 1}, timeout=5)
        if logs.status_code == 404:
            pytest.skip("LOCAL_MODE is not enabled — set LOCAL_MODE=true in .env and restart.")
        logs.raise_for_status()
    except httpx.HTTPStatusError as exc:
        pytest.skip(f"LOCAL_MODE endpoint not available: {exc}")


def _poll_until(
    fn: object,
    *,
    timeout: int,
    description: str,
) -> object:
    """Call fn() every _POLL_INTERVAL seconds until it returns a truthy value or timeout."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        result = fn()  # type: ignore[operator]
        if result:
            return result
        time.sleep(_POLL_INTERVAL)
    pytest.fail(f"Timed out after {timeout}s waiting for: {description}")


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def client() -> httpx.Client:
    with httpx.Client(timeout=10) as c:
        _check_prerequisites(c)
        yield c  # type: ignore[misc]


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestLogBridgeDetection:
    """Verify that the log-bridge detects exceptions from container stdout."""

    def test_logs_endpoint_is_reachable(self, client: httpx.Client) -> None:
        resp = client.get(_api("/api/v1/local/logs"), params={"limit": 10})
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)

    def test_dev_throw_returns_500(self, client: httpx.Client) -> None:
        marker = f"prereq-check-{uuid.uuid4().hex[:6]}"
        resp = client.get(_api("/api/v1/local/dev/throw"), params={"marker": marker})
        assert resp.status_code == 500, (
            f"Expected 500 from /dev/throw, got {resp.status_code}. "
            "Is LOCAL_MODE=true and the API container running?"
        )


class TestFullBridgePipeline:
    """Full end-to-end: exception → log-bridge → incident → dashboard data."""

    def test_exception_creates_incident(self, client: httpx.Client) -> None:
        """
        Trigger a real Python exception in the API container.
        The log-bridge should detect the traceback and create an incident.
        """
        marker = f"bridge-e2e-{uuid.uuid4().hex[:8]}"

        # Trigger exception in the API container
        throw_resp = client.get(
            _api("/api/v1/local/dev/throw"), params={"marker": marker}, timeout=10
        )
        assert throw_resp.status_code == 500

        # Poll until the incident appears in /api/v1/incidents
        def _find_incident() -> dict | None:
            resp = client.get(_api("/api/v1/incidents"), params={"page_size": 50})
            if resp.status_code != 200:
                return None
            for item in resp.json().get("items", []):
                if marker in item.get("exception_message", ""):
                    return item  # type: ignore[return-value]
            return None

        incident = _poll_until(
            _find_incident,
            timeout=_BRIDGE_TIMEOUT,
            description=f"incident with marker '{marker}' to appear in /api/v1/incidents",
        )

        assert incident is not None
        assert incident["exception_type"] == "ValueError", (
            f"Expected 'ValueError', got '{incident['exception_type']}'"
        )
        assert incident["status"] in ("new", "triaging", "analyzed", "bug_created")

    def test_exception_line_appears_in_logs_endpoint(self, client: httpx.Client) -> None:
        """
        The log-bridge should store the raw log line in Redis, and
        GET /api/v1/local/logs should return it with is_exception=True.
        """
        marker = f"logs-e2e-{uuid.uuid4().hex[:8]}"

        # Trigger exception
        client.get(_api("/api/v1/local/dev/throw"), params={"marker": marker}, timeout=10)

        # Poll until the exception log line appears
        def _find_log_line() -> dict | None:
            resp = client.get(_api("/api/v1/local/logs"), params={"limit": 200})
            if resp.status_code != 200:
                return None
            for entry in resp.json():
                if entry.get("is_exception") and marker in entry.get("line", ""):
                    return entry  # type: ignore[return-value]
            return None

        log_entry = _poll_until(
            _find_log_line,
            timeout=_BRIDGE_TIMEOUT,
            description=f"exception log line with marker '{marker}' in /api/v1/local/logs",
        )

        assert log_entry is not None
        assert log_entry["is_exception"] is True
        assert log_entry["container"] == "api"
        assert log_entry["level"] in ("ERROR", "CRITICAL")

    def test_exception_log_line_links_to_incident(self, client: httpx.Client) -> None:
        """
        The log line's incident_id should point to a real incident in the DB.
        """
        marker = f"link-e2e-{uuid.uuid4().hex[:8]}"
        client.get(_api("/api/v1/local/dev/throw"), params={"marker": marker}, timeout=10)

        def _find_linked_entry() -> dict | None:
            resp = client.get(_api("/api/v1/local/logs"), params={"limit": 200})
            if resp.status_code != 200:
                return None
            for entry in resp.json():
                if (
                    entry.get("is_exception")
                    and marker in entry.get("line", "")
                    and entry.get("incident_id")
                ):
                    return entry  # type: ignore[return-value]
            return None

        log_entry = _poll_until(
            _find_linked_entry,
            timeout=_BRIDGE_TIMEOUT,
            description=f"log line with incident_id for marker '{marker}'",
        )

        incident_id = log_entry["incident_id"]
        detail_resp = client.get(_api(f"/api/v1/incidents/{incident_id}"))
        assert detail_resp.status_code == 200, (
            f"incident_id {incident_id} from log entry not found in /api/v1/incidents"
        )
        detail = detail_resp.json()
        assert marker in detail["exception_message"]

    def test_deduplication_prevents_duplicate_incidents(self, client: httpx.Client) -> None:
        """
        Calling /dev/throw twice with the same marker should produce only ONE ValueError
        incident (fingerprint deduplication in POST /api/v1/local/ingest).

        Note: each call also generates an HTTPException incident from the uvicorn 5xx
        access-log line, but those have unique messages (port/timestamp vary) so are
        intentionally NOT deduplicated. We assert only the ValueError count.
        """
        marker = f"dedup-e2e-{uuid.uuid4().hex[:8]}"

        # Trigger same ValueError exception twice in quick succession
        client.get(_api("/api/v1/local/dev/throw"), params={"marker": marker}, timeout=10)
        time.sleep(1)
        client.get(_api("/api/v1/local/dev/throw"), params={"marker": marker}, timeout=10)

        def _find_valueerror_incidents() -> list:
            resp = client.get(_api("/api/v1/incidents"), params={"page_size": 100})
            if resp.status_code != 200:
                return []
            return [
                i
                for i in resp.json().get("items", [])
                if marker in i.get("exception_message", "")
                and i.get("exception_type") == "ValueError"
            ]

        _poll_until(
            lambda: _find_valueerror_incidents(),
            timeout=_BRIDGE_TIMEOUT,
            description=f"at least one ValueError incident with marker '{marker}'",
        )

        time.sleep(5)  # Allow second trigger's dedup to process

        valueerror_incidents = _find_valueerror_incidents()
        assert len(valueerror_incidents) == 1, (
            f"Expected exactly 1 ValueError incident (deduplication), found {len(valueerror_incidents)}"
        )


class TestAgentPipeline:
    """Verify the LocalIncidentPoller runs the LangGraph pipeline.

    Skipped automatically if AZURE_OPENAI_ENDPOINT is not configured,
    since the pipeline requires a real LLM.
    """

    @pytest.fixture(autouse=True)
    def require_openai(self, client: httpx.Client) -> None:
        if not os.environ.get("AZURE_OPENAI_ENDPOINT"):
            pytest.skip("AZURE_OPENAI_ENDPOINT not set — skipping pipeline tests")

    def test_incident_transitions_to_analyzed(self, client: httpx.Client) -> None:
        """
        After the log-bridge creates an incident, the LocalIncidentPoller should
        run the agent pipeline and transition status to 'analyzed'.
        """
        marker = f"pipeline-e2e-{uuid.uuid4().hex[:8]}"
        client.get(_api("/api/v1/local/dev/throw"), params={"marker": marker}, timeout=10)

        # Wait for incident to appear first
        def _find_incident() -> dict | None:
            resp = client.get(_api("/api/v1/incidents"), params={"page_size": 50})
            if resp.status_code != 200:
                return None
            for item in resp.json().get("items", []):
                if marker in item.get("exception_message", ""):
                    return item  # type: ignore[return-value]
            return None

        incident = _poll_until(
            _find_incident,
            timeout=_BRIDGE_TIMEOUT,
            description=f"incident with marker '{marker}'",
        )
        incident_id = incident["id"]

        # Now wait for pipeline to complete
        def _is_analyzed() -> bool:
            resp = client.get(_api(f"/api/v1/incidents/{incident_id}"))
            if resp.status_code != 200:
                return False
            status = resp.json().get("status", "")
            return status not in ("new", "triaging")

        _poll_until(
            _is_analyzed,
            timeout=_PIPELINE_TIMEOUT,
            description=f"incident {incident_id} to leave 'new'/'triaging' status",
        )

        detail = client.get(_api(f"/api/v1/incidents/{incident_id}")).json()
        assert detail["status"] in (
            "analyzed",
            "bug_created",
        ), f"Expected 'analyzed' or 'bug_created', got '{detail['status']}'"
        assert detail.get("root_cause") is not None, "Pipeline should have written a root_cause"
        assert isinstance(detail.get("recommendations"), list)
        assert len(detail["recommendations"]) >= 1
