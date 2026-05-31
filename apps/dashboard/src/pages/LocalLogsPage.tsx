import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { useNavigate } from 'react-router-dom'
import { clsx } from 'clsx'
import { Terminal, RefreshCw } from 'lucide-react'
import { fetchLocalLogs } from '../api/localLogs'
import { Card } from '../components/ui/Card'
import { EmptyState } from '../components/ui/EmptyState'
import { PageHeader } from '../components/ui/PageHeader'
import type { LogLine } from '../types/localLogs'

const CONTAINERS = ['', 'api', 'worker', 'dashboard']

const LEVEL_META: Record<string, { color: string; bg: string }> = {
  ERROR:    { color: '#ef4444', bg: 'rgba(239,68,68,0.08)' },
  CRITICAL: { color: '#dc2626', bg: 'rgba(220,38,38,0.12)' },
  WARNING:  { color: '#f59e0b', bg: 'rgba(245,158,11,0.06)' },
  WARN:     { color: '#f59e0b', bg: 'rgba(245,158,11,0.06)' },
  INFO:     { color: 'var(--color-text-1)', bg: 'transparent' },
  DEBUG:    { color: 'var(--color-text-3)', bg: 'transparent' },
}

function getLevelMeta(level: string) {
  return LEVEL_META[level.toUpperCase()] ?? { color: 'var(--color-text-1)', bg: 'transparent' }
}

function LogRow({ log, onIncidentClick }: { log: LogLine; onIncidentClick: (id: string) => void }) {
  const meta = getLevelMeta(log.level)
  return (
    <div
      className="grid grid-cols-1 gap-1.5 border-b border-border px-4 py-2.5 font-mono text-[11px] transition-colors sm:grid-cols-[130px_90px_70px_1fr_auto] sm:items-baseline sm:gap-3"
      style={{ backgroundColor: meta.bg }}
    >
      <span className="text-text-3 tabular-nums">{new Date(log.ts).toLocaleTimeString()}</span>
      <span
        className="rounded px-1.5 py-0.5 text-center text-[10px] font-medium"
        style={{
          backgroundColor: 'var(--color-surface-2)',
          color: 'var(--color-text-2)',
          border: '1px solid var(--color-border)',
        }}
      >
        {log.container}
      </span>
      <span className="font-semibold uppercase tracking-wider text-[10px]" style={{ color: meta.color }}>
        {log.level.toUpperCase().slice(0, 7)}
      </span>
      <span className="break-all leading-relaxed" style={{ color: log.is_exception ? '#ef4444' : 'var(--color-text-1)' }}>
        {log.line}
      </span>
      {log.is_exception && log.incident_id && (
        <button
          type="button"
          onClick={() => onIncidentClick(log.incident_id!)}
          className="justify-self-start rounded-md px-2 py-1 text-[10px] font-semibold transition-colors"
          style={{
            backgroundColor: 'rgba(239,68,68,0.12)',
            color: '#ef4444',
            border: '1px solid rgba(239,68,68,0.25)',
          }}
        >
          Incident →
        </button>
      )}
    </div>
  )
}

const SELECT_CLS =
  'h-9 rounded-md border border-border bg-surface px-3 text-sm text-text-1 shadow-xs focus:outline-none focus:ring-2 focus:ring-accent hover:border-border-2 transition-colors'

export function LocalLogsPage() {
  const navigate = useNavigate()
  const [container, setContainer] = useState('')
  const [autoRefresh, setAutoRefresh] = useState(true)

  const { data, isLoading, isError } = useQuery({
    queryKey: ['local-logs', container],
    queryFn: () => fetchLocalLogs({ container: container || undefined, limit: 200 }),
    refetchInterval: autoRefresh ? 2000 : false,
    staleTime: 0,
  })

  const exceptionCount = data?.filter((l) => l.is_exception).length ?? 0

  return (
    <div className="space-y-5">
      <PageHeader
        eyebrow="Observability"
        title="Container Logs"
        subtitle="Real-time local bridge stream from Docker containers."
        actions={
          <div className="flex flex-wrap items-center gap-2">
            {exceptionCount > 0 && (
              <span
                className="inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-xs font-semibold"
                style={{
                  backgroundColor: 'rgba(239,68,68,0.10)',
                  color: '#ef4444',
                  boxShadow: '0 0 0 1px rgba(239,68,68,0.25)',
                }}
              >
                ● {exceptionCount} exception{exceptionCount !== 1 ? 's' : ''}
              </span>
            )}
            <select
              value={container}
              onChange={(e) => setContainer(e.target.value)}
              className={SELECT_CLS}
            >
              {CONTAINERS.map((c) => (
                <option key={c} value={c} className="bg-surface text-text-1">
                  {c === '' ? 'All containers' : c}
                </option>
              ))}
            </select>
            <label className="inline-flex h-9 cursor-pointer items-center gap-2 rounded-md border border-border bg-surface px-3 text-sm text-text-2 shadow-xs hover:border-border-2 hover:text-text-1 transition-colors">
              <input
                type="checkbox"
                checked={autoRefresh}
                onChange={(e) => setAutoRefresh(e.target.checked)}
                className="h-3.5 w-3.5 accent-[var(--color-accent)]"
              />
              <RefreshCw className={clsx('h-3 w-3 shrink-0', autoRefresh && 'animate-spin')} style={{ animationDuration: '3s' }} />
              Live
            </label>
          </div>
        }
      />

      <Card className="overflow-hidden">
        {/* Toolbar */}
        <div className="flex flex-wrap items-center justify-between gap-2 border-b border-border bg-surface-2 px-4 py-2.5">
          <div className="flex items-center gap-2 text-xs text-text-2">
            <Terminal className="h-3.5 w-3.5" />
            <span>Last 200 lines · newest first</span>
          </div>
          <span className="rounded-full bg-success/10 px-2.5 py-0.5 text-[10px] font-semibold uppercase tracking-widest text-success">
            LOCAL_MODE
          </span>
        </div>

        {/* Log content */}
        {isLoading && (
          <p className="px-6 py-10 text-center text-sm text-text-2">Loading logs…</p>
        )}
        {isError && (
          <EmptyState
            title="Failed to load logs"
            description="Ensure LOCAL_MODE=true and API is reachable."
          />
        )}
        {data && data.length === 0 && (
          <EmptyState
            icon={Terminal}
            title="No log lines yet"
            description="The log-bridge container is tailing Docker stdout."
          />
        )}
        {data && data.length > 0 && (
          <div className="max-h-[68vh] overflow-y-auto">
            {data.map((log, index) => (
              <LogRow
                key={index}
                log={log}
                onIncidentClick={(id) => navigate(`/incidents/${id}`)}
              />
            ))}
          </div>
        )}
      </Card>
    </div>
  )
}
