"""Unit tests for the local log bridge exception parser.

These tests run without Docker or any live services — they verify the regex
state machine that turns raw container log lines into DetectedExcepion objects.
"""

from __future__ import annotations

from apps.log_bridge.exception_parser import DetectedExcepion, ExceptionParser


class TestTraceback:
    def test_detects_simple_traceback(self) -> None:
        parser = ExceptionParser()
        lines = [
            "Traceback (most recent call last):",
            '  File "/app/apps/api/main.py", line 42, in handle',
            "    result = await do_work()",
            "ValueError: something went wrong",
        ]
        result: DetectedExcepion | None = None
        for line in lines:
            result = parser.feed(line)
        assert result is not None
        assert result.exception_type == "ValueError"
        assert result.exception_message == "something went wrong"
        assert "Traceback" in result.stack_trace
        assert 'File "/app/apps/api/main.py"' in result.stack_trace

    def test_detects_nested_exception_type(self) -> None:
        parser = ExceptionParser()
        lines = [
            "Traceback (most recent call last):",
            '  File "/app/pkg/module.py", line 10, in run',
            "    raise RuntimeError('db is down')",
            "RuntimeError: db is down",
        ]
        result = None
        for line in lines:
            result = parser.feed(line)
        assert result is not None
        assert result.exception_type == "RuntimeError"
        assert result.exception_message == "db is down"

    def test_detects_dotted_exception_type(self) -> None:
        parser = ExceptionParser()
        lines = [
            "Traceback (most recent call last):",
            '  File "x.py", line 1, in f',
            "    raise app.errors.DatabaseConnectionError('timeout')",
            "app.errors.DatabaseConnectionError: timeout",
        ]
        result = None
        for line in lines:
            result = parser.feed(line)
        assert result is not None
        assert result.exception_type == "app.errors.DatabaseConnectionError"

    def test_no_result_until_traceback_complete(self) -> None:
        parser = ExceptionParser()
        result = parser.feed("Traceback (most recent call last):")
        assert result is None
        result = parser.feed('  File "x.py", line 1, in f')
        assert result is None

    def test_resets_after_complete_traceback(self) -> None:
        parser = ExceptionParser()
        first_lines = [
            "Traceback (most recent call last):",
            '  File "x.py", line 1, in f',
            "ValueError: first",
        ]
        for line in first_lines:
            parser.feed(line)

        second_lines = [
            "Traceback (most recent call last):",
            '  File "y.py", line 2, in g',
            "KeyError: 'missing_key'",
        ]
        result = None
        for line in second_lines:
            result = parser.feed(line)
        assert result is not None
        assert result.exception_type == "KeyError"

    def test_resets_on_runaway_traceback(self) -> None:
        """Parser should not accumulate unboundedly if traceback never ends."""
        parser = ExceptionParser()
        parser.feed("Traceback (most recent call last):")
        for i in range(65):
            r = parser.feed(f"  line {i} in frame")
        # After exceeding the cap, parser resets; a new traceback should work
        parser.feed("Traceback (most recent call last):")
        r = parser.feed('  File "z.py", line 1, in h')
        r = parser.feed("TypeError: wrong type")
        assert r is not None
        assert r.exception_type == "TypeError"

    def test_strips_timestamp_prefix(self) -> None:
        parser = ExceptionParser()
        lines = [
            "2026-05-24T12:00:00Z Traceback (most recent call last):",
            '2026-05-24T12:00:00Z   File "/app/x.py", line 1, in f',
            "2026-05-24T12:00:00Z AttributeError: 'NoneType' object",
        ]
        result = None
        for line in lines:
            result = parser.feed(line)
        assert result is not None
        assert result.exception_type == "AttributeError"

    def test_strips_log_level_prefix(self) -> None:
        parser = ExceptionParser()
        lines = [
            "ERROR Traceback (most recent call last):",
            'ERROR   File "/app/x.py", line 1, in f',
            "ERROR ValueError: bad value",
        ]
        result = None
        for line in lines:
            result = parser.feed(line)
        assert result is not None
        assert result.exception_type == "ValueError"


class TestSingleLine:
    def test_detects_single_line_exception(self) -> None:
        parser = ExceptionParser()
        result = parser.feed("ValueError: bad value here")
        assert result is not None
        assert result.exception_type == "ValueError"
        assert result.exception_message == "bad value here"
        assert result.stack_trace == ""

    def test_ignores_ordinary_log_line(self) -> None:
        parser = ExceptionParser()
        result = parser.feed("INFO:     Application startup complete.")
        assert result is None

    def test_ignores_empty_line(self) -> None:
        parser = ExceptionParser()
        assert parser.feed("") is None
        assert parser.feed("   ") is None

    def test_does_not_false_positive_on_partial_match(self) -> None:
        parser = ExceptionParser()
        # "error" in lowercase should not match
        result = parser.feed("no error here at all")
        assert result is None


class TestHttp5xx:
    def test_detects_http_500_in_uvicorn_log(self) -> None:
        parser = ExceptionParser()
        line = '172.18.0.1:54321 - "GET /api/v1/incidents HTTP/1.1" 500 Internal Server Error'
        result = parser.feed(line)
        assert result is not None
        assert result.exception_type == "HTTPException"
        assert "500" in result.exception_message

    def test_detects_http_502(self) -> None:
        parser = ExceptionParser()
        line = '10.0.0.1:12345 - "POST /api/v1/ingest HTTP/1.1" 502 '
        result = parser.feed(line)
        assert result is not None
        assert result.exception_type == "HTTPException"

    def test_ignores_http_200(self) -> None:
        parser = ExceptionParser()
        line = '10.0.0.1:12345 - "GET /health HTTP/1.1" 200 OK'
        result = parser.feed(line)
        assert result is None

    def test_ignores_http_404(self) -> None:
        parser = ExceptionParser()
        line = '10.0.0.1:12345 - "GET /notfound HTTP/1.1" 404 Not Found'
        result = parser.feed(line)
        assert result is None


class TestDotNet:
    def test_detects_dotnet_exception(self) -> None:
        parser = ExceptionParser()
        lines = [
            "2026-05-26 11:13:14.4031|ERROR|Middleware|An unhandled exception has occurred. System.InvalidOperationException: SampleApp unhandled exception",
            "   at API.Controllers.HealthController.ThrowException() in /src/API/Controllers/HealthController.cs:line 36",
            "   at lambda_method38(Closure, Object, Object[])",
            "2026-05-26 11:13:16.6537|INFO|Listener|Broadcasting TrendingUpdated",
        ]
        result = None
        for line in lines:
            r = parser.feed(line)
            if r:
                result = r
        assert result is not None
        assert result.exception_type == "System.InvalidOperationException"
        assert result.exception_message == "SampleApp unhandled exception"
        assert "ThrowException" in result.stack_trace


class TestJsonLogs:
    """Verify that structured JSON log lines are unwrapped before parsing."""

    def test_serilog_message_field(self) -> None:
        """Serilog JSON format: RenderedMessage contains the exception string."""
        import json

        parser = ExceptionParser()
        payload = json.dumps(
            {
                "@timestamp": "2026-05-27T08:00:00Z",
                "@l": "Error",
                "RenderedMessage": "System.NullReferenceException: Object not set to an instance of an object",
                "SourceContext": "API.Services.OrderService",
            }
        )
        result = parser.feed(payload)
        assert result is not None
        assert result.exception_type == "System.NullReferenceException"
        assert "Object not set" in result.exception_message

    def test_serilog_exception_field(self) -> None:
        """Serilog JSON format: Exception field contains the full stack trace."""
        import json

        parser = ExceptionParser()
        payload = json.dumps(
            {
                "@l": "Error",
                "message": "Unhandled error",
                "Exception": (
                    "System.InvalidOperationException: Sequence contains no elements\n"
                    "   at API.Controllers.ItemController.Get() in /src/API/Controllers/ItemController.cs:line 22"
                ),
            }
        )
        result = parser.feed(payload)
        assert result is not None
        assert result.exception_type == "System.InvalidOperationException"
        assert "Sequence contains no elements" in result.exception_message

    def test_python_structlog_json(self) -> None:
        """Python structlog JSON output: event field holds the exception text."""
        import json

        parser = ExceptionParser()
        lines = [
            json.dumps({"level": "error", "event": "Traceback (most recent call last):"}),
            json.dumps({"level": "error", "event": '  File "src/worker.py", line 10, in run'}),
            json.dumps({"level": "error", "event": "RuntimeError: queue full"}),
        ]
        result = None
        for line in lines:
            r = parser.feed(line)
            if r:
                result = r
        assert result is not None
        assert result.exception_type == "RuntimeError"
        assert result.exception_message == "queue full"

    def test_plain_text_unchanged(self) -> None:
        """Non-JSON lines should still be parsed as before (no regression)."""
        parser = ExceptionParser()
        result = parser.feed("ValueError: plain text error with no json wrapper")
        assert result is not None
        assert result.exception_type == "ValueError"
