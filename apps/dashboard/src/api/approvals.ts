import client from './client'
import type { ApprovalResponse } from '../types/incident'

export interface ApproveRequest {
  recommendation_rank: number
  approved_by: string
}

export interface RejectRequest {
  rejected_by: string
  reason?: string
}

export async function approveIncident(
  incidentId: string,
  body: ApproveRequest,
): Promise<ApprovalResponse> {
  const { data } = await client.post<ApprovalResponse>(
    `/incidents/${incidentId}/approve`,
    body,
  )
  return data
}

export async function rejectIncident(
  incidentId: string,
  body: RejectRequest,
): Promise<ApprovalResponse> {
  const { data } = await client.post<ApprovalResponse>(
    `/incidents/${incidentId}/reject`,
    body,
  )
  return data
}
