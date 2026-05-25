from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Application
    app_env: str = "development"
    log_level: str = "INFO"
    correlation_id_header: str = "X-Correlation-ID"

    # Database
    postgres_host: str = "localhost"
    postgres_port: int = 5432
    postgres_db: str = "remediai"
    postgres_user: str = "remediai"
    postgres_password: str = "change_me_locally"

    # Redis
    redis_url: str = "redis://localhost:6379/0"

    # Azure OpenAI
    azure_openai_endpoint: str = ""
    azure_openai_deployment: str = "gpt-4o"
    azure_openai_api_version: str = "2024-08-01-preview"

    # Azure DevOps
    azure_devops_org_url: str = ""
    azure_devops_project: str = ""
    azure_devops_repository: str = ""
    azure_devops_branch: str = "main"
    azure_devops_pat: str = ""

    # Azure AI Search
    azure_search_endpoint: str = ""
    azure_search_index: str = "remediai-rag"
    azure_search_api_key: str = ""
    search_index_name: str = "remediai-incidents"
    openai_embedding_model: str = "text-embedding-3-small"
    openai_embedding_deployment: str = ""
    ado_source_repo: str = ""
    ado_source_path_prefix: str = "src/"

    # Azure Monitor
    azure_monitor_workspace_id: str = ""
    azure_monitor_app_insights_resource_id: str = ""

    # Ingestion
    ingestion_poll_interval_seconds: int = 60
    ingestion_lookback_minutes: int = 10

    # Local dev mode
    local_mode: bool = False
    local_log_bridge_containers: str = "api,worker,dashboard"
    local_incident_poll_interval_seconds: int = 10

    @property
    def database_url(self) -> str:
        return (
            f"postgresql+asyncpg://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )


@lru_cache
def get_settings() -> Settings:
    return Settings()
