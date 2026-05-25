from pydantic import BaseModel


class IntegrationStatus(BaseModel):
    provider_id: str
    configured: bool
    warning: str | None = None


class IntegrationsHealthResponse(BaseModel):
    llm_provider_id: str
    retrieval_provider_id: str
    scm: IntegrationStatus
    ticketing: IntegrationStatus
    warnings: list[str]
