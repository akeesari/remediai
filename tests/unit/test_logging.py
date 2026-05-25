"""Unit tests for packages.observability.logging."""

from __future__ import annotations

import io
import json
import logging

import pytest
import structlog
import structlog.contextvars
import structlog.testing

from packages.observability.logging import configure_logging


def _make_capturing_handler() -> tuple[logging.Handler, io.StringIO]:
    buf = io.StringIO()
    handler = logging.StreamHandler(buf)
    return handler, buf


def _configure_json_capture(service: str) -> io.StringIO:
    """Configure structlog with JSON renderer and return a StringIO capturing output."""
    buf = io.StringIO()
    handler = logging.StreamHandler(buf)

    shared_processors: list[structlog.types.Processor] = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.ExceptionRenderer(),
    ]

    structlog.configure(
        processors=[*shared_processors, structlog.stdlib.ProcessorFormatter.wrap_for_formatter],
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=False,
    )

    formatter = structlog.stdlib.ProcessorFormatter(
        processors=[
            structlog.stdlib.ProcessorFormatter.remove_processors_meta,
            structlog.processors.JSONRenderer(),
        ],
        foreign_pre_chain=shared_processors,
    )
    handler.setFormatter(formatter)

    root = logging.getLogger()
    root.handlers = [handler]
    root.setLevel(logging.DEBUG)

    structlog.contextvars.clear_contextvars()
    structlog.contextvars.bind_contextvars(service=service)

    return buf


class TestJsonOutputFields:
    def test_json_output_contains_required_fields(self) -> None:
        buf = _configure_json_capture("test-service")

        log = structlog.get_logger("test")
        log.info("test_event_required_fields")

        buf.seek(0)
        line = buf.readline().strip()
        assert line, "no log output captured"

        record: dict[str, object] = json.loads(line)
        assert "timestamp" in record
        assert record["level"] == "info"
        assert record["event"] == "test_event_required_fields"
        assert record["service"] == "test-service"

    def test_extra_fields_are_preserved(self) -> None:
        buf = _configure_json_capture("svc")

        log = structlog.get_logger("test")
        log.info("thing_happened", incident_id="i-001", priority="high")

        buf.seek(0)
        record: dict[str, object] = json.loads(buf.readline().strip())
        assert record["incident_id"] == "i-001"
        assert record["priority"] == "high"


class TestCorrelationIdBinding:
    def setup_method(self) -> None:
        structlog.contextvars.clear_contextvars()

    def test_correlation_id_bound_per_request(self) -> None:
        buf = _configure_json_capture("svc")

        structlog.contextvars.bind_contextvars(correlation_id="corr-aaa")
        structlog.get_logger().info("req_a")

        structlog.contextvars.clear_contextvars()
        structlog.contextvars.bind_contextvars(correlation_id="corr-bbb")
        structlog.get_logger().info("req_b")

        buf.seek(0)
        lines = [json.loads(line) for line in buf.readlines() if line.strip()]
        assert len(lines) == 2
        assert lines[0]["correlation_id"] == "corr-aaa"
        assert lines[1]["correlation_id"] == "corr-bbb"
        assert lines[0]["correlation_id"] != lines[1]["correlation_id"]


class TestIncidentIdBinding:
    def setup_method(self) -> None:
        structlog.contextvars.clear_contextvars()

    def test_incident_id_bound_in_agent_context(self) -> None:
        buf = _configure_json_capture("agent-svc")
        structlog.contextvars.bind_contextvars(incident_id="inci-xyz-789")
        structlog.get_logger().info("agent_step_complete", agent="triage")

        buf.seek(0)
        record: dict[str, object] = json.loads(buf.readline().strip())
        assert record["incident_id"] == "inci-xyz-789"
        assert record["agent"] == "triage"


class TestConsoleFormat:
    def test_console_format_when_env_set(self) -> None:
        """LOG_FORMAT=console produces non-JSON ConsoleRenderer output."""
        buf = io.StringIO()
        handler = logging.StreamHandler(buf)

        structlog.configure(
            processors=[
                structlog.contextvars.merge_contextvars,
                structlog.stdlib.add_log_level,
                structlog.processors.TimeStamper(fmt="iso"),
                structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
            ],
            logger_factory=structlog.stdlib.LoggerFactory(),
            wrapper_class=structlog.stdlib.BoundLogger,
            cache_logger_on_first_use=False,
        )
        formatter = structlog.stdlib.ProcessorFormatter(
            processors=[
                structlog.stdlib.ProcessorFormatter.remove_processors_meta,
                structlog.dev.ConsoleRenderer(colors=False),
            ],
        )
        handler.setFormatter(formatter)

        root = logging.getLogger()
        root.handlers = [handler]
        root.setLevel(logging.DEBUG)

        structlog.contextvars.clear_contextvars()
        structlog.get_logger().info("console_event")

        buf.seek(0)
        output = buf.read()
        assert output.strip(), "no console output"
        with pytest.raises(json.JSONDecodeError):
            json.loads(output.strip())


class TestConfigureLoggingIntegration:
    def setup_method(self) -> None:
        structlog.contextvars.clear_contextvars()

    def test_configure_logging_binds_service(self) -> None:
        configure_logging("integration-svc", log_level="DEBUG", log_format="console")
        ctx = structlog.contextvars.get_contextvars()
        assert ctx.get("service") == "integration-svc"

    def test_configure_logging_json_format_does_not_raise(self) -> None:
        configure_logging("json-svc", log_level="INFO", log_format="json")
        structlog.get_logger().info("json_startup")
