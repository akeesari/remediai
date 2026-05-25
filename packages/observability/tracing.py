from __future__ import annotations

import structlog
from opentelemetry import trace
from opentelemetry.propagate import set_global_textmap
from opentelemetry.sdk.resources import SERVICE_NAME, Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.trace.propagation.tracecontext import TraceContextTextMapPropagator

logger = structlog.get_logger(__name__)

_configured = False


def configure_tracing(
    service_name: str,
    *,
    connection_string: str = "",
    otlp_endpoint: str = "",
) -> None:
    """Initialise the global OTel TracerProvider for a service.

    Idempotent — safe to call multiple times; only the first call has effect.
    Exporters are registered only when their credentials/endpoints are provided,
    so the function is safe to call in local dev with no Azure connection string.
    """
    global _configured
    if _configured:
        return
    _configured = True

    resource = Resource.create({SERVICE_NAME: service_name})
    provider = TracerProvider(resource=resource)

    if connection_string:
        try:
            from azure.monitor.opentelemetry.exporter import (
                AzureMonitorTraceExporter,
            )

            azure_exporter = AzureMonitorTraceExporter(connection_string=connection_string)
            provider.add_span_processor(BatchSpanProcessor(azure_exporter))
            logger.info("tracing_azure_monitor_exporter_registered", service=service_name)
        except ImportError:
            logger.warning("tracing_azure_monitor_exporter_unavailable")

    if otlp_endpoint:
        try:
            from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import (
                OTLPSpanExporter,
            )

            otlp_exporter = OTLPSpanExporter(endpoint=otlp_endpoint)
            provider.add_span_processor(BatchSpanProcessor(otlp_exporter))
            logger.info("tracing_otlp_exporter_registered", endpoint=otlp_endpoint)
        except ImportError:
            logger.warning("tracing_otlp_exporter_unavailable")

    trace.set_tracer_provider(provider)
    set_global_textmap(TraceContextTextMapPropagator())

    _instrument_fastapi()
    _instrument_sqlalchemy()

    logger.info("tracing_configured", service=service_name)


def _instrument_fastapi() -> None:
    try:
        from opentelemetry.instrumentation.fastapi import (
            FastAPIInstrumentor,
        )

        FastAPIInstrumentor().instrument()
    except ImportError:
        pass


def _instrument_sqlalchemy() -> None:
    try:
        from opentelemetry.instrumentation.sqlalchemy import (
            SQLAlchemyInstrumentor,
        )

        SQLAlchemyInstrumentor().instrument()
    except ImportError:
        pass


def reset_for_testing() -> None:
    """Reset the configured flag so tests can call configure_tracing repeatedly."""
    global _configured
    _configured = False
