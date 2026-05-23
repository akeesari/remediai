"""Regex-based PII scrubber applied to exception payloads before storage and LLM calls."""
from __future__ import annotations

import re

_EMAIL = re.compile(r"\b[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}\b")
_IPV4 = re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b")
_IPV6 = re.compile(
    r"\b(?:[0-9a-fA-F]{1,4}:){7}[0-9a-fA-F]{1,4}\b"
    r"|\b(?:[0-9a-fA-F]{1,4}:){1,7}:\b"
    r"|\b::(?:[0-9a-fA-F]{1,4}:){0,6}[0-9a-fA-F]{1,4}\b"
)
# Azure subscription IDs appear in resource paths: /subscriptions/<uuid>/...
_SUBSCRIPTION_ID = re.compile(
    r"(?i)(?<=/subscriptions/)[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}"
)
# Azure Storage SAS tokens: sig=<base64>
_SAS_TOKEN = re.compile(r"(?i)(?<=sig=)[A-Za-z0-9%+/=]+")
# Freestanding UUIDs that are not part of a known path segment (likely user/session IDs)
_FREESTANDING_UUID = re.compile(
    r"(?<![/\-a-fA-F0-9])"
    r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}"
    r"(?![/\-a-fA-F0-9])"
)

_RULES: list[tuple[re.Pattern[str], str]] = [
    (_EMAIL, "[EMAIL]"),
    (_IPV4, "[IP]"),
    (_IPV6, "[IP]"),
    (_SUBSCRIPTION_ID, "[SUBSCRIPTION_ID]"),
    (_SAS_TOKEN, "[SAS_TOKEN]"),
    (_FREESTANDING_UUID, "[UUID]"),
]


def scrub(text: str) -> str:
    """Return *text* with all recognised PII patterns replaced by placeholder tokens."""
    for pattern, replacement in _RULES:
        text = pattern.sub(replacement, text)
    return text
