import client from './client'
import type {
  DiscoveredTarget,
  MonitorTarget,
  TargetEnvironment,
  UpsertTargetsRequest,
  UpsertTargetsResponse,
} from '../types/targets'

export async function listTargets(
  environment: TargetEnvironment,
  enabledOnly = false,
): Promise<MonitorTarget[]> {
  const { data } = await client.get<MonitorTarget[]>('/targets', {
    params: { environment, enabled_only: enabledOnly || undefined },
  })
  return data
}

export async function listDiscoveredTargets(
  environment: TargetEnvironment,
): Promise<DiscoveredTarget[]> {
  const { data } = await client.get<DiscoveredTarget[]>('/targets/discovered', {
    params: { environment },
  })
  return data
}

export async function upsertTargets(
  payload: UpsertTargetsRequest,
): Promise<UpsertTargetsResponse> {
  const { data } = await client.put<UpsertTargetsResponse>('/targets', payload)
  return data
}
