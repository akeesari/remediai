import client from './client'
import type {
  DiscoveredTarget,
  MonitorTarget,
  TargetEnvironment,
  UpsertTargetsRequest,
  UpsertTargetsResponse,
} from '../types/targets'

function _targetAuthHeaders(): Record<string, string> | undefined {
  const token = import.meta.env.VITE_TARGETS_API_TOKEN as string | undefined
  if (!token) {
    return undefined
  }
  return { 'X-Remediai-Admin-Token': token }
}

export async function listTargets(
  environment: TargetEnvironment,
  enabledOnly = false,
): Promise<MonitorTarget[]> {
  const { data } = await client.get<MonitorTarget[]>('/targets', {
    params: { environment, enabled_only: enabledOnly || undefined },
    headers: _targetAuthHeaders(),
  })
  return data
}

export async function listDiscoveredTargets(
  environment: TargetEnvironment,
): Promise<DiscoveredTarget[]> {
  const { data } = await client.get<DiscoveredTarget[]>('/targets/discovered', {
    params: { environment },
    headers: _targetAuthHeaders(),
  })
  return data
}

export async function upsertTargets(
  payload: UpsertTargetsRequest,
): Promise<UpsertTargetsResponse> {
  const { data } = await client.put<UpsertTargetsResponse>('/targets', payload, {
    headers: _targetAuthHeaders(),
  })
  return data
}
