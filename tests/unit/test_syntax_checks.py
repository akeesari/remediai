"""Unit tests for validation_agent syntax_checks."""

from __future__ import annotations

import pytest

from packages.agent_runtime.validation_agent.syntax_checks import run_syntax_checks


def _status_map(content: str, language: str = "python") -> dict[str, str]:
    return {c.check_name: c.status for c in run_syntax_checks(content, language)}


# ---------------------------------------------------------------------------
# Python AST checks
# ---------------------------------------------------------------------------


def test_valid_python_passes() -> None:
    code = "def hello():\n    return 42\n"
    m = _status_map(code, "python")
    assert m["syntax_valid"] == "pass"
    assert m["bracket_balance"] == "pass"


def test_python_syntax_error_fails() -> None:
    bad = "def hello(\n    return 42\n"
    m = _status_map(bad, "python")
    assert m["syntax_valid"] == "fail"


def test_python_unclosed_bracket_caught_by_ast() -> None:
    bad = "x = [1, 2, 3\n"
    m = _status_map(bad, "python")
    # ast.parse will catch this
    assert m["syntax_valid"] == "fail"


def test_valid_python_with_class() -> None:
    code = (
        "class Service:\n"
        "    def process(self, value: int | None) -> str:\n"
        "        if value is None:\n"
        "            raise ValueError('value required')\n"
        "        return str(value)\n"
    )
    m = _status_map(code, "python")
    assert m["syntax_valid"] == "pass"
    assert m["bracket_balance"] == "pass"


# ---------------------------------------------------------------------------
# Bracket balance (all languages)
# ---------------------------------------------------------------------------


def test_unbalanced_brace_warns() -> None:
    code = "public class Foo { public void Bar() { return; }"
    m = _status_map(code, "dotnet")
    assert m["bracket_balance"] == "warn"


def test_unmatched_close_warns() -> None:
    code = "function foo() { return x; }}"
    m = _status_map(code, "nodejs")
    assert m["bracket_balance"] == "warn"


def test_balanced_dotnet_passes() -> None:
    code = "public class Foo {\n    public void Bar() {\n        return;\n    }\n}\n"
    m = _status_map(code, "dotnet")
    assert m["bracket_balance"] == "pass"


# ---------------------------------------------------------------------------
# Non-Python languages skip AST
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("language", ["dotnet", "nodejs", "java", "unknown"])
def test_non_python_syntax_check_passes(language: str) -> None:
    code = "some code here"
    m = _status_map(code, language)
    # Should not fail — real syntax check requires build tools
    assert m["syntax_valid"] == "pass"


# ---------------------------------------------------------------------------
# Empty content
# ---------------------------------------------------------------------------


def test_empty_content_returns_pass() -> None:
    checks = run_syntax_checks("", "python")
    assert all(c.status == "pass" for c in checks)
