from __future__ import annotations

from collections.abc import Callable

from langchain_core.language_models.chat_models import BaseChatModel

from packages.integrations.providers.base import ProviderConfig

_AZURE_FOUNDRY_PROFILE = "azure-foundry"
_PORTABLE_PROFILE = "portable"

_ALLOWED_LLM_PROVIDERS: dict[str, set[str]] = {
    _AZURE_FOUNDRY_PROFILE: {"azure-openai"},
    _PORTABLE_PROFILE: {"portable-openai", "stub-chat", "azure-openai"},
}


def provider_config_from_settings(settings: object) -> ProviderConfig:
    """Resolve provider selection from settings with stable defaults."""
    return ProviderConfig(
        profile=str(getattr(settings, "remediai_profile", _AZURE_FOUNDRY_PROFILE)),
        llm_provider_id=str(getattr(settings, "llm_provider_id", "azure-openai")),
        retrieval_provider_id=str(getattr(settings, "retrieval_provider_id", "azure-ai-search")),
        scm_provider_id=resolve_scm_provider_id(settings),
        ticket_provider_id=resolve_ticket_provider_id(settings),
    )


def ensure_valid_provider_config(settings: object) -> ProviderConfig:
    """Validate provider selection and return normalized config."""
    cfg = provider_config_from_settings(settings)

    if cfg.profile not in _ALLOWED_LLM_PROVIDERS:
        allowed = ", ".join(sorted(_ALLOWED_LLM_PROVIDERS))
        raise ValueError(f"Unknown remediai_profile '{cfg.profile}'. Allowed: {allowed}")

    if cfg.llm_provider_id not in _ALLOWED_LLM_PROVIDERS[cfg.profile]:
        allowed_llms = ", ".join(sorted(_ALLOWED_LLM_PROVIDERS[cfg.profile]))
        raise ValueError(
            "Unsupported llm_provider_id "
            f"'{cfg.llm_provider_id}' for profile '{cfg.profile}'. Allowed: {allowed_llms}"
        )

    return cfg


def create_chat_model(settings: object) -> BaseChatModel:
    """Create chat model from provider selection."""
    cfg = ensure_valid_provider_config(settings)

    factories: dict[str, Callable[[object], BaseChatModel]] = {
        "azure-openai": _create_azure_chat_model,
        "portable-openai": _create_portable_chat_model,
        "stub-chat": _create_stub_chat_model,
    }

    factory = factories.get(cfg.llm_provider_id)
    if factory is None:
        raise ValueError(f"Unknown llm_provider_id '{cfg.llm_provider_id}'")
    return factory(settings)


def resolve_scm_provider_id(settings: object) -> str:
    raw = str(getattr(settings, "scm_provider_id", "auto") or "auto").strip().lower()
    if raw in {"", "auto"}:
        return "azure-devops" if _has_ado_repo_settings(settings) else "none"
    if raw in {"none", "disabled"}:
        return "none"
    return raw


def resolve_ticket_provider_id(settings: object) -> str:
    raw = str(getattr(settings, "ticket_provider_id", "none") or "none").strip().lower()
    if raw in {"none", "disabled"}:
        return "none"
    if raw in {"", "auto"}:
        return "azure-devops-boards" if _has_ado_boards_settings(settings) else "none"
    return raw


def is_scm_configured(settings: object) -> bool:
    provider_id = resolve_scm_provider_id(settings)
    if provider_id == "none":
        return False
    if provider_id == "azure-devops":
        return _has_ado_repo_settings(settings)
    return True


def is_ticketing_configured(settings: object) -> bool:
    provider_id = resolve_ticket_provider_id(settings)
    if provider_id == "none":
        return False
    if provider_id == "azure-devops-boards":
        return _has_ado_boards_settings(settings)
    return True


def integration_warnings(settings: object) -> list[str]:
    warnings: list[str] = []
    if not is_scm_configured(settings):
        warnings.append(
            "Source control integration is not configured. Code context, PR creation, and validation are skipped."
        )
    if not is_ticketing_configured(settings):
        warnings.append("External ticketing is disabled.")
    return warnings


def _has_ado_repo_settings(settings: object) -> bool:
    org_url = str(getattr(settings, "azure_devops_org_url", "") or "").strip()
    project = str(getattr(settings, "azure_devops_project", "") or "").strip()
    repository = str(getattr(settings, "azure_devops_repository", "") or "").strip()
    return bool(org_url and project and repository)


def _has_ado_boards_settings(settings: object) -> bool:
    org_url = str(getattr(settings, "azure_devops_org_url", "") or "").strip()
    project = str(getattr(settings, "azure_devops_project", "") or "").strip()
    return bool(org_url and project)


def _create_azure_chat_model(settings: object) -> BaseChatModel:
    from packages.integrations.providers.azure_foundry.llm import create_chat_model

    return create_chat_model(settings)


def _create_portable_chat_model(settings: object) -> BaseChatModel:
    from packages.integrations.providers.portable.llm import create_openai_compatible_chat_model

    return create_openai_compatible_chat_model(settings)


def _create_stub_chat_model(settings: object) -> BaseChatModel:
    from packages.integrations.providers.portable.llm import create_stub_chat_model

    return create_stub_chat_model(settings)
