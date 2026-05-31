"""Language-aware syntax validation for AI-generated code patches.

All checks run in-process — no subprocess, no shell execution, no network calls.
For Python: ast.parse() gives a real syntax verdict.
For other languages: bracket balance catches the most common generation mistakes.
"""

from __future__ import annotations

import ast

from packages.agent_runtime.validation_agent.models import ValidationCheck


def run_syntax_checks(patched_content: str, language: str) -> list[ValidationCheck]:
    """Return syntax validation checks for *patched_content* in *language*."""
    if not patched_content:
        return [
            ValidationCheck(
                check_name="syntax_valid",
                status="pass",
                detail="No patched content to validate.",
            )
        ]

    checks: list[ValidationCheck] = []
    checks.append(_check_syntax(patched_content, language))
    checks.append(_check_bracket_balance(patched_content))
    return checks


def _check_syntax(content: str, language: str) -> ValidationCheck:
    if language == "python":
        return _check_python_syntax(content)
    # For non-Python languages we can't do a real parse without external tools.
    # Return an informational pass rather than a false signal.
    return ValidationCheck(
        check_name="syntax_valid",
        status="pass",
        detail=f"Syntax check skipped for {language} (requires build tools).",
    )


def _check_python_syntax(content: str) -> ValidationCheck:
    """Use ast.parse() to verify the Python source is syntactically valid."""
    try:
        ast.parse(content)
        return ValidationCheck(
            check_name="syntax_valid",
            status="pass",
            detail="Python AST parse succeeded — no syntax errors detected.",
        )
    except SyntaxError as exc:
        line_info = f" (line {exc.lineno})" if exc.lineno else ""
        return ValidationCheck(
            check_name="syntax_valid",
            status="fail",
            detail=f"Python syntax error{line_info}: {exc.msg}",
        )
    except ValueError as exc:
        return ValidationCheck(
            check_name="syntax_valid",
            status="fail",
            detail=f"Python parse failed: {exc}",
        )


def _check_bracket_balance(content: str) -> ValidationCheck:
    """Check that all bracket pairs are balanced."""
    pairs = {"(": ")", "[": "]", "{": "}"}
    stack: list[str] = []
    for ch in content:
        if ch in pairs:
            stack.append(pairs[ch])
        elif ch in pairs.values():
            if not stack or stack[-1] != ch:
                return ValidationCheck(
                    check_name="bracket_balance",
                    status="warn",
                    detail=f"Unmatched closing bracket '{ch}' found in patched content.",
                )
            stack.pop()
    if stack:
        return ValidationCheck(
            check_name="bracket_balance",
            status="warn",
            detail=f"Unclosed bracket(s) in patched content: expecting {stack[-1]!r}.",
        )
    return ValidationCheck(
        check_name="bracket_balance",
        status="pass",
        detail="All bracket pairs are balanced.",
    )
