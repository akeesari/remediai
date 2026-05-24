"""Regex-based PII scrubber applied to exception payloads before storage and LLM calls."""
from __future__ import annotations

import re
from typing import Any

# Patterns applied in order — most specific first to avoid overlapping replacements.
_EMAIL = re.compile(r"\b[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}\b")
_BEARER_TOKEN = re.compile(r"Bearer\s+\S+", re.IGNORECASE)
# Azure Blob/ADLS SAS signature value (after sig=)
_SAS_TOKEN = re.compile(r"(?i)(?<=sig=)[A-Za-z0-9%+/=]+")
# Azure subscription ID inside resource paths — matched before generic UUID
_SUBSCRIPTION_ID = re.compile(
    r"(?i)(?<=/subscriptions/)"
    r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}"
)
_IPV6 = re.compile(
    r"(?:"
    r"[0-9a-fA-F]{1,4}(?::[0-9a-fA-F]{1,4}){7}"
    r"|(?:[0-9a-fA-F]{1,4}:){1,7}:"
    r"|(?:[0-9a-fA-F]{1,4}:){1,6}:[0-9a-fA-F]{1,4}"
    r"|(?:[0-9a-fA-F]{1,4}:){1,5}(?::[0-9a-fA-F]{1,4}){1,2}"
    r"|(?:[0-9a-fA-F]{1,4}:){1,4}(?::[0-9a-fA-F]{1,4}){1,3}"
    r"|(?:[0-9a-fA-F]{1,4}:){1,3}(?::[0-9a-fA-F]{1,4}){1,4}"
    r"|(?:[0-9a-fA-F]{1,4}:){1,2}(?::[0-9a-fA-F]{1,4}){1,5}"
    r"|[0-9a-fA-F]{1,4}:(?::[0-9a-fA-F]{1,4}){1,6}"
    r"|::(?:[0-9a-fA-F]{1,4}:){0,6}[0-9a-fA-F]{1,4}"
    r"|::[0-9a-fA-F]{1,4}"
    r")"
)
_IPV4 = re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b")
# Freestanding UUIDs (likely user/session IDs) — after subscription ID pattern
_FREESTANDING_UUID = re.compile(
    r"(?<![/\-a-fA-F0-9])"
    r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}"
    r"(?![/\-a-fA-F0-9])"
)
_CREDIT_CARD = re.compile(r"\b\d{4}[- ]?\d{4}[- ]?\d{4}[- ]?\d{4}\b")
# Windows username in path: C:\Users\<username>\...
_WINDOWS_USERNAME = re.compile(r"(C:\\Users\\)[^\\]+", re.IGNORECASE)

_RULES: list[tuple[re.Pattern[str], str]] = [
    (_BEARER_TOKEN, "Bearer [TOKEN]"),
    (_SAS_TOKEN, "[SAS_TOKEN]"),
    (_SUBSCRIPTION_ID, "[SUBSCRIPTION_ID]"),
    (_EMAIL, "[EMAIL]"),
    (_IPV6, "[IP]"),
    (_IPV4, "[IP]"),
    (_FREESTANDING_UUID, "[UUID]"),
    (_CREDIT_CARD, "[CC]"),
    (_WINDOWS_USERNAME, r"\1[USERNAME]"),
]


class PiiScrubber:
    """Applies ordered regex substitutions to mask PII in text.

    Stateless and thread-safe — all patterns are compiled at class definition time.
    """

    _rules = _RULES

    def scrub(self, text: str) -> str:
        """Return *text* with all recognised PII patterns replaced by placeholder tokens."""
        for pattern, replacement in self._rules:
            text = pattern.sub(replacement, text)
        return text

    def scrub_dict(self, data: dict[str, Any]) -> dict[str, Any]:
        """Recursively scrub all string values in *data*; non-string values pass through."""
        return {k: self._scrub_value(v) for k, v in data.items()}

    def _scrub_value(self, value: Any) -> Any:
        if isinstance(value, str):
            return self.scrub(value)
        if isinstance(value, dict):
            return self.scrub_dict(value)
        if isinstance(value, list):
            return [self._scrub_value(item) for item in value]
        return value


_DEFAULT_SCRUBBER = PiiScrubber()


def scrub(text: str) -> str:
    """Return *text* with all recognised PII patterns replaced by placeholder tokens."""
    return _DEFAULT_SCRUBBER.scrub(text)
