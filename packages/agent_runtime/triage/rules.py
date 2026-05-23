"""Rule-based triage classification for known .NET exception types.

Rules are ordered by severity: higher-severity rules appear first so a single
exception type is never downgraded by a later, lower-severity generic rule.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass
class TriageRule:
    patterns: list[str]
    labels: list[str]
    priority: str


@dataclass
class RuleMatch:
    labels: list[str]
    priority: str
    matched: bool


_RULES: list[TriageRule] = [
    # --- critical ---
    TriageRule(
        patterns=["OutOfMemoryException", "StackOverflowException"],
        labels=["resource-exhaustion"],
        priority="critical",
    ),
    TriageRule(
        patterns=[
            "UnauthorizedAccessException",
            "AuthenticationException",
            "SecurityException",
            "ForbiddenException",
        ],
        labels=["authentication"],
        priority="critical",
    ),
    # --- high ---
    TriageRule(
        patterns=["TimeoutException", "TaskCanceledException", "OperationCanceledException"],
        labels=["timeout"],
        priority="high",
    ),
    TriageRule(
        patterns=["SqlException", "DbUpdateException", "DbUpdateConcurrencyException"],
        labels=["database"],
        priority="high",
    ),
    TriageRule(
        patterns=["HttpRequestException", "WebException", "SocketException"],
        labels=["network"],
        priority="high",
    ),
    TriageRule(
        patterns=["NullReferenceException"],
        labels=["null-reference"],
        priority="high",
    ),
    # --- medium ---
    TriageRule(
        patterns=["ArgumentNullException", "ArgumentException", "ArgumentOutOfRangeException"],
        labels=["argument-validation"],
        priority="medium",
    ),
    TriageRule(
        patterns=["InvalidOperationException"],
        labels=["invalid-operation"],
        priority="medium",
    ),
    TriageRule(
        patterns=["FileNotFoundException", "DirectoryNotFoundException", "IOException"],
        labels=["file-system"],
        priority="medium",
    ),
    TriageRule(
        patterns=["FormatException", "InvalidCastException", "OverflowException"],
        labels=["data-conversion"],
        priority="medium",
    ),
    TriageRule(
        patterns=["KeyNotFoundException"],
        labels=["missing-key"],
        priority="medium",
    ),
    TriageRule(
        patterns=["ObjectDisposedException"],
        labels=["object-disposed"],
        priority="medium",
    ),
    # --- low ---
    TriageRule(
        patterns=["NotImplementedException"],
        labels=["not-implemented"],
        priority="low",
    ),
]


def apply_rules(exception_type: str) -> RuleMatch:
    """Return the first matching rule or an unmatched result with default priority."""
    for rule in _RULES:
        if any(pattern in exception_type for pattern in rule.patterns):
            return RuleMatch(labels=list(rule.labels), priority=rule.priority, matched=True)
    return RuleMatch(labels=[], priority="medium", matched=False)
