import client from './client'
import type { IntegrationsHealthResponse } from '../types/integrations'

export async function getIntegrationsHealth(): Promise<IntegrationsHealthResponse> {
  const { data } = await client.get<IntegrationsHealthResponse>('/integrations/health')
  return data
}