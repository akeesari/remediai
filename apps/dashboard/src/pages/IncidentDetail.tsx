import { useState } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { getIncident } from '../api/incidents'
import { approveIncident, rejectIncident } from '../api/approvals'
import { Badge, priorityVariant, statusVariant } from '../components/ui/Badge'
import { Button } from '../components/ui/Button'
import { Card } from '../components/ui/Card'
import { EmptyState } from '../components/ui/EmptyState'
import { PageHeader } from '../components/ui/PageHeader'
import { SkeletonBlock } from '../components/ui/SkeletonBlock'
import type { AgentTraceEntry, Recommendation } from '../types/incident'

export function IncidentDetail() {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const [selectedRank, setSelectedRank] = useState<number | null>(null)

  const { data, isLoading, isError } = useQuery({
    queryKey: ['incident', id],
    queryFn: () => getIncident(id!),
    enabled: !!id,
  })

  const approveMutation = useMutation({
    mutationFn: () =>
      approveIncident(id!, {
        recommendation_rank: selectedRank!,
        approved_by: 'engineer',
      }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['incident', id] }),
  })

  const rejectMutation = useMutation({
    mutationFn: () =>
      rejectIncident(id!, { rejected_by: 'engineer', reason: 'Rejected via dashboard.' }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['incident', id] }),
  })

  if (isLoading) {
    return (
      <div className="space-y-3">
        <SkeletonBlock className="h-12" />
        <SkeletonBlock className="h-32" />
        <SkeletonBlock className="h-32" />
      </div>
    )
  }

  if (isError || !data) {
    return <EmptyState title="Failed to load incident" description="Try opening it from the incidents list again." />
  }

  const shortType = data.exception_type.split('.').pop() ?? data.exception_type

  return (
    <div className="space-y-4">
      <PageHeader
        title={shortType}
        subtitle={data.exception_message}
        actions={
          <>
            <Badge text={data.priority} variant={priorityVariant(data.priority)} />
            <Badge text={data.status} variant={statusVariant(data.status)} />
            <Button type="button" onClick={() => navigate(-1)}>
              Back
            </Button>
          </>
        }
      />

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-5">
        <div className="space-y-4 lg:col-span-3">
          {data.root_cause && (
            <Card className="p-5">
              <h2 className="mb-3 text-sm font-semibold uppercase tracking-wide text-text-2">Root Cause</h2>
              <p className="text-sm leading-relaxed text-text-1">{data.root_cause}</p>
              {data.root_cause_json && (
                <dl className="mt-4 grid grid-cols-1 gap-3 sm:grid-cols-2">
                  <Stat label="Component" value={data.root_cause_json.component} />
                  <Stat
                    label="Confidence"
                    value={`${Math.round(data.root_cause_json.confidence * 100)}%`}
                  />
                  <div className="sm:col-span-2">
                    <dt className="text-xs font-medium text-text-2">Likely Cause</dt>
                    <dd className="mt-1 text-sm text-text-1">{data.root_cause_json.likely_cause}</dd>
                  </div>
                </dl>
              )}
            </Card>
          )}

          {data.recommendations.length > 0 && (
            <Card className="p-5">
              <h2 className="mb-3 text-sm font-semibold uppercase tracking-wide text-text-2">Recommendations</h2>
              <ol className="space-y-3">
                {data.recommendations.map((rec: Recommendation) => (
                  <li key={rec.rank} className="rounded-lg border border-border bg-surface-2 p-4">
                    <div className="flex flex-wrap items-center justify-between gap-2">
                      <p className="text-sm font-semibold text-text-1">
                        #{rec.rank} {rec.title}
                      </p>
                      <span className="rounded border border-border-2 bg-surface px-2 py-1 text-xs text-text-2">
                        {Math.round(rec.confidence * 100)}% confidence
                      </span>
                    </div>
                    <p className="mt-2 text-sm text-text-2">{rec.description}</p>
                    {rec.suggested_change && (
                      <pre className="mt-2 overflow-x-auto rounded-md border border-border bg-bg p-3 text-xs text-text-1">
                        {rec.suggested_change}
                      </pre>
                    )}
                    {rec.affected_files.length > 0 && (
                      <div className="mt-2 flex flex-wrap gap-1">
                        {rec.affected_files.map((path) => (
                          <span
                            key={path}
                            className="rounded border border-border-2 bg-surface px-2 py-1 font-mono text-xs text-text-2"
                          >
                            {path}
                          </span>
                        ))}
                      </div>
                    )}
                  </li>
                ))}
              </ol>
            </Card>
          )}

          {data.stack_trace && (
            <Card className="p-5">
              <h2 className="mb-3 text-sm font-semibold uppercase tracking-wide text-text-2">Stack Trace</h2>
              <pre className="overflow-x-auto rounded-md border border-border bg-bg p-4 text-xs leading-relaxed text-text-1">
                {data.stack_trace}
              </pre>
            </Card>
          )}
        </div>

        <div className="space-y-4 lg:col-span-2">
          {data.work_items.length > 0 && (
            <Card className="p-5">
              <h2 className="mb-3 text-sm font-semibold uppercase tracking-wide text-text-2">External Work Items</h2>
              <div className="flex flex-wrap gap-2">
                {data.work_items.map((item) => (
                  <a
                    key={item.ado_item_id}
                    href={item.ado_item_url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="rounded-md border border-border-2 bg-surface-2 px-3 py-1 text-sm text-accent transition-colors hover:text-accent-hover"
                  >
                    {item.item_type} #{item.ado_item_id}
                  </a>
                ))}
              </div>
            </Card>
          )}

          {data.recommendations.length > 0 && data.status === 'analyzed' && (
            <Card className="p-5">
              <h2 className="mb-3 text-sm font-semibold uppercase tracking-wide text-text-2">Create Pull Request</h2>
              {data.approval_status === 'approved' ? (
                <div className="space-y-2 text-sm text-text-2">
                  <p>
                    PR queued by <span className="font-medium text-text-1">{data.approved_by}</span>
                  </p>
                  {data.pr_url && (
                    <a
                      href={data.pr_url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="text-accent hover:text-accent-hover hover:underline"
                    >
                      View draft PR
                    </a>
                  )}
                </div>
              ) : (
                <div className="space-y-3">
                  <div className="space-y-2">
                    {data.recommendations.map((rec: Recommendation) => (
                      <label key={rec.rank} className="flex cursor-pointer items-center gap-2 text-sm text-text-2">
                        <input
                          type="radio"
                          name="rec_rank"
                          value={rec.rank}
                          checked={selectedRank === rec.rank}
                          onChange={() => setSelectedRank(rec.rank)}
                          className="accent-accent"
                        />
                        <span>
                          #{rec.rank} {rec.title}
                        </span>
                      </label>
                    ))}
                  </div>
                  <div className="flex flex-wrap gap-2">
                    <Button
                      type="button"
                      variant="primary"
                      disabled={selectedRank === null || approveMutation.isPending}
                      onClick={() => approveMutation.mutate()}
                    >
                      {approveMutation.isPending ? 'Queuing...' : 'Approve & Queue PR'}
                    </Button>
                    <Button
                      type="button"
                      variant="destructive"
                      disabled={rejectMutation.isPending}
                      onClick={() => rejectMutation.mutate()}
                    >
                      {rejectMutation.isPending ? 'Rejecting...' : 'Reject All'}
                    </Button>
                  </div>
                  {(approveMutation.isError || rejectMutation.isError) && (
                    <p className="text-sm text-error">Action failed. Please try again.</p>
                  )}
                </div>
              )}
            </Card>
          )}

          {data.agent_trace.length > 0 && (
            <Card className="p-5">
              <h2 className="mb-3 text-sm font-semibold uppercase tracking-wide text-text-2">Agent Trace</h2>
              <div className="space-y-2">
                {data.agent_trace.map((entry: AgentTraceEntry, index) => (
                  <div key={index} className="rounded-md border border-border bg-surface-2 p-3">
                    <div className="flex items-center justify-between gap-2">
                      <p className="text-sm font-medium capitalize text-text-1">{entry.agent_name}</p>
                      <span className="text-xs text-text-2">{entry.latency_ms} ms</span>
                    </div>
                    <p className="mt-1 font-mono text-xs text-text-3">{entry.prompt_version}</p>
                    <p className="mt-1 text-xs text-text-2">{entry.output_summary}</p>
                    {entry.error && <p className="mt-1 text-xs text-error">{entry.error}</p>}
                  </div>
                ))}
              </div>
            </Card>
          )}
        </div>
      </div>

      <p className="text-xs text-text-3">
        Created {new Date(data.created_at).toLocaleString()} - Updated {new Date(data.updated_at).toLocaleString()}
      </p>
    </div>
  )
}

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <dt className="text-xs font-medium text-text-2">{label}</dt>
      <dd className="mt-1 text-sm font-semibold text-text-1">{value}</dd>
    </div>
  )
}
