from __future__ import annotations

from types import SimpleNamespace

import pytest
from langchain_core.language_models.chat_models import BaseChatModel

from packages.integrations.providers.registry import (
    create_chat_model,
    ensure_valid_provider_config,
    integration_warnings,
    is_scm_configured,
    is_ticketing_configured,
    provider_config_from_settings,
    resolve_scm_provider_id,
    resolve_ticket_provider_id,
)


def test_provider_config_defaults_to_azure_profile() -> None:
    settings = SimpleNamespace()

    cfg = provider_config_from_settings(settings)

    assert cfg.profile == "azure-foundry"
    assert cfg.llm_provider_id == "azure-openai"


def test_invalid_profile_raises() -> None:
    settings = SimpleNamespace(remediai_profile="unknown", llm_provider_id="azure-openai")

    with pytest.raises(ValueError, match="Unknown remediai_profile"):
        ensure_valid_provider_config(settings)


def test_invalid_llm_provider_for_profile_raises() -> None:
    settings = SimpleNamespace(remediai_profile="azure-foundry", llm_provider_id="portable-openai")

    with pytest.raises(ValueError, match="Unsupported llm_provider_id"):
        ensure_valid_provider_config(settings)


def test_portable_stub_chat_model_creation() -> None:
    settings = SimpleNamespace(remediai_profile="portable", llm_provider_id="stub-chat")

    model = create_chat_model(settings)

    assert isinstance(model, BaseChatModel)


def test_scm_auto_resolves_to_none_without_ado_repo_settings() -> None:
    settings = SimpleNamespace(scm_provider_id="auto")

    assert resolve_scm_provider_id(settings) == "none"
    assert is_scm_configured(settings) is False


def test_scm_auto_resolves_to_azure_devops_with_repo_settings() -> None:
    settings = SimpleNamespace(
        scm_provider_id="auto",
        azure_devops_org_url="https://dev.azure.com/org",
        azure_devops_project="proj",
        azure_devops_repository="repo",
    )

    assert resolve_scm_provider_id(settings) == "azure-devops"
    assert is_scm_configured(settings) is True


def test_ticket_provider_none_is_supported() -> None:
    settings = SimpleNamespace(ticket_provider_id="none")

    assert resolve_ticket_provider_id(settings) == "none"
    assert is_ticketing_configured(settings) is False


def test_integration_warnings_surface_missing_scm_and_ticketing() -> None:
    settings = SimpleNamespace(scm_provider_id="none", ticket_provider_id="none")

    warnings = integration_warnings(settings)

    assert len(warnings) == 2
    assert any("Source control integration" in warning for warning in warnings)
    assert any("External ticketing" in warning for warning in warnings)
