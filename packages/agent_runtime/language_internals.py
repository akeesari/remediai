"""Language-aware framework internal prefix registry.

Single source of truth for deciding whether a stack frame method or file path
belongs to framework/library internals (and should be skipped) vs. user code
(and should be analysed).

To add a new language: add an entry to FRAMEWORK_PREFIXES — nothing else needs
to change.
"""

from __future__ import annotations

FRAMEWORK_PREFIXES: dict[str, tuple[str, ...]] = {
    "dotnet": (
        "System.",
        "Microsoft.AspNetCore.",
        "Microsoft.Extensions.",
        "Microsoft.EntityFrameworkCore.",
        "Microsoft.Azure.",
        "Azure.",
        "lambda_method",
    ),
    "python": (
        "site-packages/",
        "lib/python",
        "<frozen ",
        "importlib",
        "_pytest",
        "pluggy",
    ),
    "nodejs": (
        "node_modules/",
        "internal/",
        "<anonymous>",
        "node:internal",
    ),
    "java": (
        "java.",
        "javax.",
        "sun.",
        "com.sun.",
        "org.springframework.",
        "org.hibernate.",
        "com.fasterxml.",
    ),
    "unknown": (),
}


def is_framework_internal(method_or_path: str, language: str) -> bool:
    """Return True when *method_or_path* looks like framework/library code for *language*."""
    prefixes = FRAMEWORK_PREFIXES.get(language, ())
    return any(method_or_path.startswith(p) for p in prefixes)


def is_user_code(method_or_path: str, language: str) -> bool:
    """Return True when *method_or_path* looks like user/application code."""
    return not is_framework_internal(method_or_path, language)
