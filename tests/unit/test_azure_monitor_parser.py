"""Unit tests for the Azure Monitor KQL parser — no Azure credentials required."""
from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock

from packages.integrations.azure_monitor.parser import _extract_stack_trace, parse_exception_rows


def _make_table(rows: list[list[Any]]) -> MagicMock:
    """Build a minimal LogsTable mock with the standard exception columns."""
    column_names = [
        "timestamp",
        "operation_Id",
        "type",
        "outerMessage",
        "innermostMessage",
        "innermostType",
        "assembly",
        "method",
        "outerAssembly",
        "outerMethod",
        "details",
        "client_Type",
        "operation_Name",
        "cloud_RoleName",
        "application_Version",
        "itemId",
    ]
    table = MagicMock()
    table.columns = column_names  # LogsTable.columns is List[str]
    table.rows = rows
    return table


def _make_row(
    *,
    exc_type: str = "System.NullReferenceException",
    outer_message: str = "Object reference not set to an instance of an object.",
    cloud_role: str = "MyService",
    operation_id: str = "abc123def456",
    details: Any = None,
    innermost_type: str = "",
    innermost_message: str = "",
) -> list[Any]:
    return [
        "2024-01-15T10:00:00Z",  # timestamp
        operation_id,            # operation_Id
        exc_type,                # type
        outer_message,           # outerMessage
        innermost_message,       # innermostMessage
        innermost_type,          # innermostType
        "MyService.dll",         # assembly
        "UserService.GetById",   # method
        "MyService.dll",         # outerAssembly
        "UserController.Get",    # outerMethod
        details,                 # details
        "PC",                    # client_Type
        "GET /api/users/1",      # operation_Name
        cloud_role,              # cloud_RoleName
        "1.2.3",                 # application_Version
        "item-id-001",           # itemId
    ]


class TestParseExceptionRows:
    def test_single_valid_row_returns_one_incident(self) -> None:
        table = _make_table([_make_row()])
        incidents = parse_exception_rows(table)
        assert len(incidents) == 1

    def test_exception_type_mapped_correctly(self) -> None:
        table = _make_table([_make_row(exc_type="System.ArgumentNullException")])
        incident = parse_exception_rows(table)[0]
        assert incident.exception_type == "System.ArgumentNullException"

    def test_exception_message_mapped_correctly(self) -> None:
        msg = "Value cannot be null. (Parameter 'userId')"
        table = _make_table([_make_row(outer_message=msg)])
        incident = parse_exception_rows(table)[0]
        assert incident.exception_message == msg

    def test_source_from_cloud_role_name(self) -> None:
        table = _make_table([_make_row(cloud_role="OrderService")])
        incident = parse_exception_rows(table)[0]
        assert incident.source == "OrderService"

    def test_source_defaults_to_unknown_when_blank(self) -> None:
        table = _make_table([_make_row(cloud_role="")])
        incident = parse_exception_rows(table)[0]
        assert incident.source == "unknown"

    def test_fingerprint_is_populated(self) -> None:
        table = _make_table([_make_row()])
        incident = parse_exception_rows(table)[0]
        assert len(incident.fingerprint) == 64  # SHA-256 hex

    def test_two_identical_exceptions_produce_same_fingerprint(self) -> None:
        row = _make_row()
        table = _make_table([row, row])
        incidents = parse_exception_rows(table)
        assert incidents[0].fingerprint == incidents[1].fingerprint

    def test_different_exceptions_produce_different_fingerprints(self) -> None:
        table = _make_table([
            _make_row(exc_type="System.NullReferenceException"),
            _make_row(exc_type="System.TimeoutException"),
        ])
        incidents = parse_exception_rows(table)
        assert incidents[0].fingerprint != incidents[1].fingerprint

    def test_row_missing_type_is_skipped(self) -> None:
        row = _make_row(exc_type="", innermost_type="")
        table = _make_table([row])
        assert parse_exception_rows(table) == []

    def test_row_missing_message_is_skipped(self) -> None:
        row = _make_row(outer_message="", innermost_message="")
        table = _make_table([row])
        assert parse_exception_rows(table) == []

    def test_fallback_to_innermost_type_when_type_blank(self) -> None:
        row = _make_row(exc_type="", innermost_type="System.IO.FileNotFoundException")
        table = _make_table([row])
        incidents = parse_exception_rows(table)
        assert len(incidents) == 1
        assert incidents[0].exception_type == "System.IO.FileNotFoundException"

    def test_fallback_to_innermost_message_when_outer_blank(self) -> None:
        row = _make_row(outer_message="", innermost_message="File not found")
        table = _make_table([row])
        incidents = parse_exception_rows(table)
        assert len(incidents) == 1
        assert incidents[0].exception_message == "File not found"

    def test_empty_table_returns_empty_list(self) -> None:
        table = _make_table([])
        assert parse_exception_rows(table) == []

    def test_pii_scrubbed_from_exception_message(self) -> None:
        msg = "User admin@corp.com caused error at 10.0.0.1"
        table = _make_table([_make_row(outer_message=msg)])
        incident = parse_exception_rows(table)[0]
        assert "@" not in incident.exception_message
        assert "10.0.0.1" not in incident.exception_message

    def test_raw_payload_populated(self) -> None:
        table = _make_table([_make_row(cloud_role="TestService")])
        incident = parse_exception_rows(table)[0]
        assert isinstance(incident.raw_payload, dict)
        assert incident.raw_payload  # non-empty


class TestExtractStackTrace:
    def test_none_returns_none(self) -> None:
        assert _extract_stack_trace(None) is None

    def test_empty_string_returns_none(self) -> None:
        assert _extract_stack_trace("") is None

    def test_plain_string_passthrough(self) -> None:
        trace = "at MyApp.Service.Method() in Service.cs:line 42"
        result = _extract_stack_trace(trace)
        assert result == trace

    def test_json_string_parsed(self) -> None:
        details = '[{"message": "at MyApp.Service.Method() in Service.cs:line 42"}]'
        result = _extract_stack_trace(details)
        assert result is not None
        assert "MyApp.Service.Method" in result

    def test_list_with_parsed_stack(self) -> None:
        details = [
            {
                "parsedStack": [
                    {"assembly": "MyApp", "method": "Service.Run", "fileName": "Service.cs", "line": 10},
                ]
            }
        ]
        result = _extract_stack_trace(details)
        assert result is not None
        assert "Service.Run" in result

    def test_invalid_json_string_returned_as_is(self) -> None:
        trace = "not json at all"
        result = _extract_stack_trace(trace)
        assert result == trace
