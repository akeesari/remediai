from __future__ import annotations

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_openai import AzureChatOpenAI


def create_chat_model(settings: object) -> BaseChatModel:
    """Create the default Azure OpenAI/Foundry chat model."""
    return AzureChatOpenAI(
        azure_endpoint=getattr(settings, "azure_openai_endpoint", ""),
        azure_deployment=getattr(settings, "azure_openai_deployment", "gpt-4o"),
        api_version=getattr(settings, "azure_openai_api_version", "2024-08-01-preview"),
        temperature=0,
    )
