"""Unit tests for the exception intake endpoints (Gap 4)."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from apps.api.routers.exceptions import _create_incident
from apps.api.schemas.exception_intake import ExceptionIngestPayload


def _mock_db(existing: object = None) -> MagicMock:
    db = MagicMock()
    db.scalar = AsyncMock(return_value=existing)
    db.add = MagicMock()
    db.commit = AsyncMock()
    return db


def _payload(**overrides: object) -> ExceptionIngestPayload:
    base = ExceptionIngestPayload(
        exception_type="NullReferenceException",
        exception_message="Object reference not set.",
        stack_trace="   at MyApp.Service.Run() in src/Service.cs:line 42",
        source="payment-api",
        application_name="payment-api",
        environment="production",
        language="dotnet",
    )
    for k, v in overrides.items():
        object.__setattr__(base, k, v)
    return base


@pytest.mark.asyncio
async def test_new_exception_creates_incident() -> None:
    db = _mock_db(existing=None)
    response = await _create_incident(_payload(), db)
    assert response.status == "created"
    assert response.incident_id is not None
    db.add.assert_called_once()
    db.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_duplicate_exception_returns_duplicate_status() -> None:
    existing_orm = MagicMock()
    db = _mock_db(existing=existing_orm)
    response = await _create_incident(_payload(), db)
    assert response.status == "duplicate"
    assert response.incident_id is None
    db.add.assert_not_called()


@pytest.mark.asyncio
async def test_different_source_does_not_affect_fingerprint_logic() -> None:
    db = _mock_db(existing=None)
    p = _payload(source="different-source")
    response = await _create_incident(p, db)
    assert response.status == "created"


@pytest.mark.asyncio
async def test_empty_stack_trace_accepted() -> None:
    db = _mock_db(existing=None)
    p = _payload(stack_trace="")
    response = await _create_incident(p, db)
    assert response.status == "created"


@pytest.mark.asyncio
async def test_python_exception_accepted() -> None:
    db = _mock_db(existing=None)
    p = _payload(
        exception_type="AttributeError",
        exception_message="'NoneType' object has no attribute 'charge'",
        stack_trace='  File "/app/src/payment.py", line 42, in charge',
        language="python",
    )
    response = await _create_incident(p, db)
    assert response.status == "created"
