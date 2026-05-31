from functools import lru_cache

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Application
    app_env: str = "development"
    log_level: str = "INFO"
    correlation_id_header: str = "X-Correlation-ID"

    # Database — supply DATABASE_URL in env; default is local-dev only
    database_url: str = "postgresql+asyncpg://remediai:change_me_locally@localhost:5432/remediai"

    # Redis
    redis_url: str = "redis://localhost:6379/0"

    # Azure OpenAI
    azure_openai_endpoint: str = ""
    azure_openai_deployment: str = "gpt-4.1"
    azure_openai_api_version: str = "2024-08-01-preview"

    # Provider profile (Phase 32)
    remediai_profile: str = "azure-foundry"
    llm_provider_id: str = "azure-openai"
    retrieval_provider_id: str = "azure-ai-search"
    scm_provider_id: str = "auto"
    ticket_provider_id: str = "none"

    # Portable OpenAI-compatible provider credentials.
    # In production these values must come from secret management (Key Vault).
    portable_openai_base_url: str = ""
    portable_openai_api_key: SecretStr = SecretStr("")
    portable_openai_model: str = "gpt-4.1-mini"

    # Azure DevOps
    azure_devops_org_url: str = ""
    azure_devops_project: str = ""
    azure_devops_repository: str = ""
    azure_devops_branch: str = "main"
    azure_devops_pat: SecretStr = SecretStr("")

    # Azure AI Search
    azure_search_endpoint: str = ""
    azure_search_index: str = "remediai-rag"
    azure_search_api_key: SecretStr = SecretStr("")
    azure_search_incidents_index: str = "remediai-incidents"
    openai_embedding_model: str = "text-embedding-3-small"
    openai_embedding_deployment: str = ""
    ado_source_path_prefix: str = "src/"
    # File extension for source code indexing (Phase 36: language-agnostic)
    # Override per language: .cs (dotnet), .py (python), .ts/.js (nodejs), .java (java)
    source_file_extension: str = ".cs"

    # Azure Monitor
    azure_monitor_workspace_id: str = ""

    # Ingestion
    ingestion_poll_interval_seconds: int = 60
    ingestion_lookback_minutes: int = 10

    # CORS — comma-separated list of allowed origins.
    # Set to the dashboard origin in production; empty string disables CORS.
    cors_origins: str = "http://localhost:3000"

    # Local dev mode
    local_mode: bool = False
    bridge_containers: str = "api,worker,dashboard"
    local_incident_poll_interval_seconds: int = 10
    kubernetes_discovery_namespaces: str = ""
    kubernetes_discovery_workloads: str = ""
    target_api_token: str = "local-dev-target-token"
    # Bearer token required on all API routes when set.
    # Leave empty in local dev to disable auth. Must be set in production.
    api_bearer_token: SecretStr = SecretStr("")


@lru_cache
def get_settings() -> Settings:
    return Settings()
