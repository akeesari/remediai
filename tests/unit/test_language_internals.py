"""Unit tests for language_internals — is_framework_internal / is_user_code."""

from __future__ import annotations

import pytest

from packages.agent_runtime.language_internals import is_framework_internal, is_user_code


@pytest.mark.parametrize(
    "method_or_path,language,expected_internal",
    [
        # .NET internals
        ("System.Linq.Enumerable.First", "dotnet", True),
        ("Microsoft.AspNetCore.Mvc.Controller", "dotnet", True),
        ("Azure.Core.Pipeline.HttpPipeline", "dotnet", True),
        ("lambda_method", "dotnet", True),
        # .NET user code
        ("MyApp.Services.OrderService.CompleteCheckout", "dotnet", False),
        ("PaymentService.Charge", "dotnet", False),
        # Python internals
        ("site-packages/sqlalchemy/engine.py", "python", True),
        ("lib/python3.12/json/__init__.py", "python", True),
        ("<frozen importlib._bootstrap>", "python", True),
        # Python user code
        ("src/services/order_service.py", "python", False),
        ("app/models/order.py", "python", False),
        # Node.js internals
        ("node_modules/axios/lib/core/Axios.js", "nodejs", True),
        ("internal/process/task_queues.js", "nodejs", True),
        # Node.js user code
        ("src/services/OrderService.js", "nodejs", False),
        ("app/routes/orders.ts", "nodejs", False),
        # Java internals
        ("java.util.ArrayList.add", "java", True),
        ("org.springframework.web.servlet.DispatcherServlet.doDispatch", "java", True),
        ("com.sun.proxy.$Proxy12.invoke", "java", True),
        # Java user code
        ("com.example.services.OrderService.completeCheckout", "java", False),
        ("io.myapp.OrderController.create", "java", False),
        # Unknown language — no prefixes match
        ("anything.at.all", "unknown", False),
    ],
)
def test_is_framework_internal(method_or_path: str, language: str, expected_internal: bool) -> None:
    assert is_framework_internal(method_or_path, language) == expected_internal


def test_is_user_code_is_inverse() -> None:
    assert is_user_code("System.String", "dotnet") is False
    assert is_user_code("MyApp.Service", "dotnet") is True
