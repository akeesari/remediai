export interface WorkItemSummary {
  ado_item_id: number
  ado_item_url: string
  item_type: string
  pr_url: string | null
}

export interface IncidentListItem {
  id: string
  exception_type: string
  exception_message: string
  priority: string
  status: string
  created_at: string
  updated_at: string
  has_analysis: boolean
  external_item_url: string | null
}

export interface AgentTraceEntry {
  agent_name: string
  prompt_version: string
  input_summary: string
  output_summary: string
  latency_ms: number
  error: string | null
}

export interface Recommendation {
  rank: number
  title: string
  description: string
  affected_files: string[]
  suggested_change: string
  confidence: number
  source_refs: string[]
}

export interface RootCauseJson {
  component: string
  likely_cause: string
  contributing_factors: string[]
  confidence: number
}

export interface IncidentDetail {
  id: string
  exception_type: string
  exception_message: string
  stack_trace: string | null
  priority: string
  status: string
  created_at: string
  updated_at: string
  root_cause: string | null
  root_cause_json: RootCauseJson | null
  recommendations: Recommendation[]
  code_snippets: unknown[]
  rag_results: unknown[]
  agent_trace: AgentTraceEntry[]
  work_items: WorkItemSummary[]
  // Phase 19 — approval gate
  approval_status: string | null
  approved_by: string | null
  approved_at: string | null
  approved_recommendation_rank: number | null
  pr_url: string | null
}

export interface ApprovalResponse {
  incident_id: string
  approval_status: string
  approved_recommendation_rank: number | null
  approved_by: string | null
  approved_at: string | null
}

export interface PaginatedResponse<T> {
  items: T[]
  total: number
  page: number
  page_size: number
  pages: number
}
