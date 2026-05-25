export type TargetEnvironment = 'local' | 'kubernetes'
export type TargetType = 'container' | 'namespace' | 'workload'

export interface MonitorTarget {
  id: string
  environment: TargetEnvironment
  target_type: TargetType
  target_key: string
  display_name: string
  enabled: boolean
  metadata: Record<string, unknown>
  created_at: string
  updated_at: string
}

export interface DiscoveredTarget {
  environment: TargetEnvironment
  target_type: TargetType
  target_key: string
  display_name: string
  metadata: Record<string, unknown>
}

export interface MonitorTargetUpsert {
  target_type: TargetType
  target_key: string
  display_name: string
  enabled: boolean
  metadata: Record<string, unknown>
}

export interface UpsertTargetsRequest {
  environment: TargetEnvironment
  targets: MonitorTargetUpsert[]
}

export interface UpsertTargetsResponse {
  updated: number
}
