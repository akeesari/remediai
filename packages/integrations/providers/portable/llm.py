from __future__ import annotations

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.language_models.fake_chat_models import FakeListChatModel
from langchain_openai import ChatOpenAI
from pydantic import SecretStr


def create_openai_compatible_chat_model(settings: object) -> BaseChatModel:
    """Create a portable OpenAI-compatible chat model."""
    raw = getattr(settings, "portable_openai_api_key", None)
    api_key: SecretStr | None
    if isinstance(raw, SecretStr):
        api_key = raw if raw.get_secret_value() else None
    elif isinstance(raw, str) and raw:
        api_key = SecretStr(raw)
    else:
        api_key = None

    return ChatOpenAI(
        model=getattr(settings, "portable_openai_model", "gpt-4o-mini"),
        base_url=getattr(settings, "portable_openai_base_url", ""),
        api_key=api_key,
        temperature=0,
    )


# Responses for stub chat model - used in order as ainvoke is called
_TRIAGE_RESPONSE = (
    '{"priority": "medium", "triage_labels": ["error-handling"], "rationale": "Test fixture"}'
)
_ROOT_CAUSE_RESPONSE = '{"root_cause_summary": "Test root cause detected", "root_cause_json": {"component": "test-service", "likely_cause": "fixture exception", "contributing_factors": [], "confidence": 0.5, "affected_namespace": ""}}'
_FIX_PLANNER_RESPONSE = '{"recommendations": [{"rank": 1, "title": "Add error handling", "description": "Wrap in try-catch", "affected_files": ["test.py"], "suggested_change": "try:\\n  pass\\nexcept Exception as e:\\n  log(e)", "confidence": 0.6, "source_refs": []}]}'


def create_stub_chat_model(_: object) -> BaseChatModel:
    """Create a deterministic stub model for local development and testing.

    Returns valid structured responses for each agent in the pipeline.
    Uses FakeListChatModel which cycles through responses as invoke is called.
    """
    # Provide multiple copies of each response to handle any processing pattern
    responses = [
        _TRIAGE_RESPONSE,
        _ROOT_CAUSE_RESPONSE,
        _FIX_PLANNER_RESPONSE,
        _TRIAGE_RESPONSE,
        _ROOT_CAUSE_RESPONSE,
        _FIX_PLANNER_RESPONSE,
        _TRIAGE_RESPONSE,
        _ROOT_CAUSE_RESPONSE,
        _FIX_PLANNER_RESPONSE,
    ]
    return FakeListChatModel(responses=responses)
