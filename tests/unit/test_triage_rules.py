"""Unit tests for the rule-based triage classifier — no LLM or DB required."""

from __future__ import annotations

from packages.agent_runtime.triage.rules import RuleMatch, apply_rules


class TestApplyRules:
    # ---- critical ----

    def test_out_of_memory_is_critical(self) -> None:
        result = apply_rules("System.OutOfMemoryException")
        assert result.matched is True
        assert result.priority == "critical"
        assert "resource-exhaustion" in result.labels

    def test_stack_overflow_is_critical(self) -> None:
        result = apply_rules("System.StackOverflowException")
        assert result.priority == "critical"

    def test_unauthorized_access_is_critical(self) -> None:
        result = apply_rules("System.UnauthorizedAccessException")
        assert result.priority == "critical"
        assert "authentication" in result.labels

    def test_security_exception_is_critical(self) -> None:
        result = apply_rules("System.Security.SecurityException")
        assert result.priority == "critical"

    # ---- high ----

    def test_timeout_exception_is_high(self) -> None:
        result = apply_rules("System.TimeoutException")
        assert result.matched is True
        assert result.priority == "high"
        assert "timeout" in result.labels

    def test_task_canceled_is_high(self) -> None:
        result = apply_rules("System.Threading.Tasks.TaskCanceledException")
        assert result.priority == "high"
        assert "timeout" in result.labels

    def test_sql_exception_is_high(self) -> None:
        result = apply_rules("Microsoft.Data.SqlClient.SqlException")
        assert result.priority == "high"
        assert "database" in result.labels

    def test_db_update_exception_is_high(self) -> None:
        result = apply_rules("Microsoft.EntityFrameworkCore.DbUpdateException")
        assert result.priority == "high"
        assert "database" in result.labels

    def test_http_request_exception_is_high(self) -> None:
        result = apply_rules("System.Net.Http.HttpRequestException")
        assert result.priority == "high"
        assert "network" in result.labels

    def test_null_reference_is_high(self) -> None:
        result = apply_rules("System.NullReferenceException")
        assert result.matched is True
        assert result.priority == "high"
        assert "null-reference" in result.labels

    # ---- medium ----

    def test_argument_null_exception_is_medium(self) -> None:
        result = apply_rules("System.ArgumentNullException")
        assert result.priority == "medium"
        assert "argument-validation" in result.labels

    def test_invalid_operation_is_medium(self) -> None:
        result = apply_rules("System.InvalidOperationException")
        assert result.priority == "medium"
        assert "invalid-operation" in result.labels

    def test_file_not_found_is_medium(self) -> None:
        result = apply_rules("System.IO.FileNotFoundException")
        assert result.priority == "medium"
        assert "file-system" in result.labels

    def test_format_exception_is_medium(self) -> None:
        result = apply_rules("System.FormatException")
        assert result.priority == "medium"
        assert "data-conversion" in result.labels

    def test_key_not_found_is_medium(self) -> None:
        result = apply_rules("System.Collections.Generic.KeyNotFoundException")
        assert result.priority == "medium"
        assert "missing-key" in result.labels

    def test_object_disposed_is_medium(self) -> None:
        result = apply_rules("System.ObjectDisposedException")
        assert result.priority == "medium"
        assert "object-disposed" in result.labels

    # ---- low ----

    def test_not_implemented_is_low(self) -> None:
        result = apply_rules("System.NotImplementedException")
        assert result.matched is True
        assert result.priority == "low"
        assert "not-implemented" in result.labels

    # ---- no match ----

    def test_unknown_exception_returns_unmatched(self) -> None:
        result = apply_rules("MyApp.CustomDomainException")
        assert result.matched is False
        assert result.labels == []
        assert result.priority == "medium"

    def test_empty_string_returns_unmatched(self) -> None:
        result = apply_rules("")
        assert result.matched is False

    def test_result_is_rule_match_type(self) -> None:
        result = apply_rules("System.NullReferenceException")
        assert isinstance(result, RuleMatch)

    def test_higher_severity_rule_wins_over_later_generic(self) -> None:
        # OutOfMemory should be critical, not shadowed by a hypothetical medium rule
        result = apply_rules("System.OutOfMemoryException")
        assert result.priority == "critical"

    def test_partial_namespace_match_works(self) -> None:
        # The pattern is a substring match; fully-qualified names should match
        result = apply_rules("System.Threading.Tasks.OperationCanceledException")
        assert result.matched is True
        assert "timeout" in result.labels
