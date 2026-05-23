from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any
from uuid import UUID, uuid4

import structlog

from packages.domain.models.incident import Incident
from packages.integrations.pii_scrubber import scrub

if TYPE_CHECKING:
    from azure.monitor.query import LogsTable

logger = structlog.get_logger()

# Columns projected by kql_queries.exceptions_kql — order matters for fallback logic.
_REQUIRED_COLUMNS = {"type", "outerMessage"}


def parse_exception_rows(table: LogsTable) -> list[Incident]:
    """Convert a KQL LogsTable into a list of Incident domain models."""
    col_names = list(table.columns)  # LogsTable.columns is List[str]
    incidents: list[Incident] = []

    for row in table.rows:
        row_dict: dict[str, Any] = dict(zip(col_names, row, strict=False))
        incident = _parse_row(row_dict)
        if incident is not None:
            incidents.append(incident)

    return incidents


def _parse_row(row: dict[str, Any]) -> Incident | None:
    exception_type = _coalesce(row.get("type"), row.get("innermostType"))
    exception_message = _coalesce(row.get("outerMessage"), row.get("innermostMessage"))

    if not exception_type or not exception_message:
        logger.warning(
            "parser_skipped_row_missing_fields",
            has_type=bool(exception_type),
            has_message=bool(exception_message),
        )
        return None

    source = str(row.get("cloud_RoleName") or "unknown")
    stack_trace = _extract_stack_trace(row.get("details"))
    correlation_id = _parse_uuid(row.get("operation_Id"))

    raw_payload = _build_raw_payload(row)

    return Incident(
        correlation_id=correlation_id,
        source=scrub(source),
        exception_type=scrub(str(exception_type)),
        exception_message=scrub(str(exception_message)),
        stack_trace=scrub(stack_trace) if stack_trace else None,
        raw_payload=raw_payload,
    )


def _coalesce(*values: Any) -> Any:
    for v in values:
        if v is not None and str(v).strip():
            return v
    return None


def _extract_stack_trace(details: Any) -> str | None:
    """Parse the App Insights 'details' dynamic column into a readable stack trace."""
    if details is None:
        return None

    if isinstance(details, str):
        try:
            details = json.loads(details)
        except json.JSONDecodeError:
            return details if details.strip() else None

    if not isinstance(details, list):
        return str(details) if details else None

    frames: list[str] = []
    for item in details:
        if isinstance(item, dict):
            parsed = item.get("parsedStack")
            if isinstance(parsed, list):
                for frame in parsed:
                    if isinstance(frame, dict):
                        assembly = frame.get("assembly", "")
                        method = frame.get("method", "")
                        file_name = frame.get("fileName", "")
                        line = frame.get("line", "")
                        line_str = f" line {line}" if line else ""
                        frames.append(f"  at {assembly}.{method} in {file_name}{line_str}")
            elif msg := item.get("message"):
                frames.append(str(msg))

    return "\n".join(frames) if frames else None


def _parse_uuid(value: Any) -> UUID:
    if value is None:
        return uuid4()
    try:
        return UUID(str(value))
    except (ValueError, AttributeError):
        return uuid4()


def _build_raw_payload(row: dict[str, Any]) -> dict[str, Any]:
    """Build a JSON-serialisable raw payload dict with PII scrubbed."""
    payload: dict[str, Any] = {}
    for key, val in row.items():
        if val is None:
            continue
        scrubbed = scrub(str(val)) if isinstance(val, str) else val
        payload[key] = scrubbed
    return payload
