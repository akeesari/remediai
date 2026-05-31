"""Unit tests for language_detector.detect_language()."""

from __future__ import annotations

import pytest

from packages.agent_runtime.language_detector import detect_language

_DOTNET_TRACE = (
    "   at MyApp.Services.OrderService.CompleteCheckout(Order order) "
    "in /app/src/Services/OrderService.cs:line 142\n"
    "   at System.Threading.Tasks.Task.RunSynchronously()"
)

_PYTHON_TRACE = (
    "Traceback (most recent call last):\n"
    '  File "/app/src/services/order_service.py", line 42, in complete_checkout\n'
    "    result = payment_client.charge(order)\n"
    "AttributeError: 'NoneType' object has no attribute 'charge'"
)

_NODEJS_TRACE = (
    "TypeError: Cannot read properties of undefined (reading 'charge')\n"
    "    at OrderService.completeCheckout (/app/src/services/OrderService.js:42:18)\n"
    "    at async handler (/app/src/routes/orders.ts:15:5)"
)

_JAVA_TRACE = (
    "java.lang.NullPointerException\n"
    "\tat com.example.services.OrderService.completeCheckout(OrderService.java:42)\n"
    "\tat com.example.controllers.OrderController.create(OrderController.java:18)"
)


@pytest.mark.parametrize(
    "exception_type,stack_trace,expected",
    [
        # .NET — via stack trace
        ("System.NullReferenceException", _DOTNET_TRACE, "dotnet"),
        # .NET — via exception type alone
        ("NullReferenceException", "", "dotnet"),
        ("OutOfMemoryException", "", "dotnet"),
        ("ArgumentNullException", "", "dotnet"),
        # Python — via stack trace
        ("AttributeError", _PYTHON_TRACE, "python"),
        # Python — via exception type alone
        ("AttributeError", "", "python"),
        ("KeyError", "", "python"),
        ("FileNotFoundError", "", "python"),
        # Python — dotted module path without a stack trace is ambiguous; unknown
        ("sqlalchemy.exc.NoResultFound", "", "unknown"),
        # Python — dotted module path WITH a stack trace is detected correctly
        ("sqlalchemy.exc.NoResultFound", _PYTHON_TRACE, "python"),
        # Node.js — via stack trace
        ("TypeError", _NODEJS_TRACE, "nodejs"),
        # Java — via stack trace
        ("NullPointerException", _JAVA_TRACE, "java"),
        # Java — via exception type alone (fully-qualified)
        ("java.lang.NullPointerException", "", "java"),
        ("java.sql.SQLException", "", "java"),
        # Java — short known names
        ("NullPointerException", "", "java"),
        ("IllegalArgumentException", "", "java"),
        # Unknown
        ("SomeObscureError", "", "unknown"),
    ],
)
def test_detect_language(exception_type: str, stack_trace: str, expected: str) -> None:
    result = detect_language(exception_type, stack_trace)
    assert result == expected, (
        f"detect_language({exception_type!r}, ...) = {result!r}, want {expected!r}"
    )


def test_stack_trace_takes_priority_over_type() -> None:
    # Stack trace says Python but exception type looks .NET — stack wins
    result = detect_language("NullReferenceException", _PYTHON_TRACE)
    assert result == "python"


def test_empty_inputs_return_unknown() -> None:
    assert detect_language("", "") == "unknown"
