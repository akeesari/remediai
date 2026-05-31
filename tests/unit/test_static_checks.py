"""Unit tests for validation static diff checks."""

from __future__ import annotations

from packages.agent_runtime.validation_agent.static_checks import run_static_checks


def _status_map(diff_text: str, language: str = "dotnet") -> dict[str, str]:
    checks = run_static_checks(diff_text, language=language)
    return {check.check_name: check.status for check in checks}


def test_detects_api_key_in_diff() -> None:
    diff = """
+api_key = \"abcdef1234567890\"
"""
    statuses = _status_map(diff)
    assert statuses["no_secrets"] == "fail"


def test_clean_diff_passes_all() -> None:
    diff = """
diff --git a/src/Service.cs b/src/Service.cs
index 1111111..2222222 100644
--- a/src/Service.cs
+++ b/src/Service.cs
@@ -1,3 +1,4 @@
 public class Service {
+    private readonly int _x = 1;
 }
"""
    statuses = _status_map(diff)
    assert all(status == "pass" for status in statuses.values())


def test_test_file_deletion_fails() -> None:
    diff = """
diff --git a/tests/OrderServiceTests.cs b/tests/OrderServiceTests.cs
index 1111111..2222222 100644
--- a/tests/OrderServiceTests.cs
+++ b/tests/OrderServiceTests.cs
@@ -2,3 +2,2 @@
-Assert.Equal(1, result);
"""
    statuses = _status_map(diff)
    assert statuses["no_test_deletion"] == "fail"


def test_large_diff_over_500_fails() -> None:
    body = "\n".join(f"+line {i}" for i in range(520))
    statuses = _status_map(body)
    assert statuses["diff_size"] == "fail"


def test_large_diff_200_500_warns() -> None:
    body = "\n".join(f"+line {i}" for i in range(250))
    statuses = _status_map(body)
    assert statuses["diff_size"] == "warn"


def test_new_dotnet_import_warns() -> None:
    diff = "+using System.Net.Http;\n"
    statuses = _status_map(diff, language="dotnet")
    assert statuses["no_new_imports"] == "warn"


def test_new_python_import_warns() -> None:
    diff = "+import requests\n"
    statuses = _status_map(diff, language="python")
    assert statuses["no_new_imports"] == "warn"


def test_no_new_imports_passes() -> None:
    diff = " existing_code = 1\n"
    statuses = _status_map(diff, language="dotnet")
    assert statuses["no_new_imports"] == "pass"
