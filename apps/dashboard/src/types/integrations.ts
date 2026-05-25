export interface IntegrationStatus {
  provider_id: string
  configured: boolean
  warning: string | null
}

export interface IntegrationsHealthResponse {
  llm_provider_id: string
  retrieval_provider_id: string
  scm: IntegrationStatus
  ticketing: IntegrationStatus
  warnings: string[]
}