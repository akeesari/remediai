from __future__ import annotations

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.language_models.fake_chat_models import FakeListChatModel
from langchain_openai import ChatOpenAI
from pydantic import SecretStr


def create_openai_compatible_chat_model(settings: object) -> BaseChatModel:
    """Create a portable OpenAI-compatible chat model."""
    raw_api_key = getattr(settings, "portable_openai_api_key", "")
    api_key: SecretStr | None
    if isinstance(raw_api_key, SecretStr):
        api_key = raw_api_key
    elif isinstance(raw_api_key, str) and raw_api_key:
        api_key = SecretStr(raw_api_key)
    else:
        api_key = None

    return ChatOpenAI(
        model=getattr(settings, "portable_openai_model", "gpt-4o-mini"),
        base_url=getattr(settings, "portable_openai_base_url", ""),
        api_key=api_key,
        temperature=0,
    )


def create_stub_chat_model(_: object) -> BaseChatModel:
    """Create a deterministic stub model for profile bootstrap tests."""
    return FakeListChatModel(responses=["{}"])
