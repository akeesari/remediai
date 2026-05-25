from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from langchain_core.language_models.chat_models import BaseChatModel


class LLMProvider(Protocol):
    """Contract for constructing chat models from app settings."""

    provider_id: str

    def create_chat_model(self, settings: object) -> BaseChatModel: ...


@dataclass(frozen=True)
class ProviderConfig:
    """Resolved provider selection from runtime settings."""

    profile: str
    llm_provider_id: str
    retrieval_provider_id: str
    scm_provider_id: str
    ticket_provider_id: str
