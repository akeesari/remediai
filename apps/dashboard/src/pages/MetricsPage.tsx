import { useQuery } from '@tanstack/react-query'
import { Bar, BarChart, Cell, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import { Activity, CheckCircle2, Percent } from 'lucide-react'
import { getMetrics } from '../api/metrics'
import { Card } from '../components/ui/Card'
import { EmptyState } from '../components/ui/EmptyState'
import { PageHeader } from '../components/ui/PageHeader'
import { SkeletonBlock } from '../components/ui/SkeletonBlock'
import { StatCard } from '../components/ui/StatCard'
import { useTheme } from '../components/shell/ThemeContext'

const PRIORITY_COLORS: Record<string, string> = {
  critical: '#ef4444',
  high:     '#f97316',
  medium:   '#eab308',
  low:      '#22c55e',
}

function useChartTheme() {
  const { theme } = useTheme()
  const dark = theme === 'dark'
  return {
    tick:    dark ? '#52525b' : '#9ca3af',
    cursor:  dark ? '#19191d' : '#f0f3f7',
    tooltip: {
      bg:     dark ? '#111113' : '#ffffff',
      border: dark ? 'rgba(255,255,255,0.08)' : 'rgba(9,9,11,0.08)',
      color:  dark ? '#fafafa' : '#0a0a0b',
    },
  }
}

export function MetricsPage() {
  const { data, isLoading, isError } = useQuery({
    queryKey: ['metrics'],
    queryFn: getMetrics,
    refetchInterval: 30_000,
  })
  const chart = useChartTheme()

  if (isLoading) {
    return (
      <div className="space-y-6 page-enter">
        <SkeletonBlock className="h-10 w-48" />
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
          {[...Array(3)].map((_, i) => <SkeletonBlock key={i} className="h-32 rounded-xl" />)}
        </div>
        <div className="grid grid-cols-1 gap-4 xl:grid-cols-2">
          {[...Array(2)].map((_, i) => <SkeletonBlock key={i} className="h-72 rounded-xl" />)}
        </div>
      </div>
    )
  }

  if (isError || !data) {
    return <EmptyState title="Failed to load metrics" description="Please retry in a few seconds." />
  }

  const analyzedPct =
    data.total_incidents > 0
      ? Math.round((data.total_analyzed / data.total_incidents) * 100)
      : 0

  const rateGradient =
    analyzedPct >= 80 ? 'success' : analyzedPct >= 50 ? 'warning' : 'error'

  return (
    <div className="space-y-7 page-enter">
      <PageHeader
        eyebrow="Analytics"
        title="Metrics"
        subtitle="High-level incident volume and AI analysis coverage."
      />

      {/* ── Gradient stat cards ── */}
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
        <StatCard
          label="Total Incidents"
          value={data.total_incidents.toLocaleString()}
          icon={Activity}
          gradient="accent"
          description="All time"
        />
        <StatCard
          label="Analyzed"
          value={data.total_analyzed.toLocaleString()}
          icon={CheckCircle2}
          gradient="success"
          description="AI processed"
        />
        <StatCard
          label="Analysis Rate"
          value={`${analyzedPct}%`}
          icon={Percent}
          gradient={rateGradient as 'success' | 'warning' | 'error'}
          description={analyzedPct >= 80 ? 'Excellent' : analyzedPct >= 50 ? 'Good' : 'Needs attention'}
        />
      </div>

      {/* ── Charts ── */}
      <div className="grid grid-cols-1 gap-4 xl:grid-cols-2">
        <ChartCard title="Incidents by Status" subtitle="Current distribution">
          <ResponsiveContainer width="100%" height={260}>
            <BarChart data={data.by_status} margin={{ top: 4, right: 4, left: -24, bottom: 0 }}>
              <XAxis
                dataKey="status"
                tick={{ fill: chart.tick, fontSize: 11, fontWeight: 500 }}
                axisLine={false}
                tickLine={false}
              />
              <YAxis
                allowDecimals={false}
                tick={{ fill: chart.tick, fontSize: 11 }}
                axisLine={false}
                tickLine={false}
              />
              <Tooltip
                cursor={{ fill: chart.cursor, rx: 6 }}
                contentStyle={{
                  backgroundColor: chart.tooltip.bg,
                  borderColor: chart.tooltip.border,
                  color: chart.tooltip.color,
                  borderRadius: 10,
                  fontSize: 12,
                  fontWeight: 500,
                  boxShadow: 'var(--shadow-lg)',
                }}
              />
              <Bar dataKey="count" fill="var(--color-accent)" radius={[6, 6, 0, 0]} maxBarSize={48} />
            </BarChart>
          </ResponsiveContainer>
        </ChartCard>

        <ChartCard title="Incidents by Priority" subtitle="Severity breakdown">
          <ResponsiveContainer width="100%" height={260}>
            <BarChart data={data.by_priority} margin={{ top: 4, right: 4, left: -24, bottom: 0 }}>
              <XAxis
                dataKey="priority"
                tick={{ fill: chart.tick, fontSize: 11, fontWeight: 500 }}
                axisLine={false}
                tickLine={false}
              />
              <YAxis
                allowDecimals={false}
                tick={{ fill: chart.tick, fontSize: 11 }}
                axisLine={false}
                tickLine={false}
              />
              <Tooltip
                cursor={{ fill: chart.cursor, rx: 6 }}
                contentStyle={{
                  backgroundColor: chart.tooltip.bg,
                  borderColor: chart.tooltip.border,
                  color: chart.tooltip.color,
                  borderRadius: 10,
                  fontSize: 12,
                  fontWeight: 500,
                  boxShadow: 'var(--shadow-lg)',
                }}
              />
              <Bar dataKey="count" radius={[6, 6, 0, 0]} maxBarSize={48}>
                {data.by_priority.map((entry) => (
                  <Cell
                    key={entry.priority}
                    fill={PRIORITY_COLORS[entry.priority] ?? 'var(--color-accent)'}
                  />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </ChartCard>
      </div>

      {/* ── Top error types ── */}
      {data.top_errors.length > 0 ? (
        <Card className="overflow-hidden">
          <div className="flex items-center justify-between border-b border-border px-6 py-4">
            <div>
              <h2 className="text-[13px] font-semibold text-text-1">Top Exception Types</h2>
              <p className="mt-0.5 text-xs text-text-3">Most frequently occurring</p>
            </div>
            <span
              className="rounded-full px-2.5 py-0.5 text-[11px] font-semibold text-white"
              style={{ background: 'var(--gradient-accent)' }}
            >
              {data.top_errors.length} types
            </span>
          </div>
          <div className="divide-y divide-border">
            {data.top_errors.map((row, i) => (
              <div
                key={row.exception_type}
                className="flex items-center justify-between px-6 py-3.5 transition-colors hover:bg-surface-2"
              >
                <div className="flex items-center gap-3 min-w-0">
                  <span className="flex h-6 w-6 shrink-0 items-center justify-center rounded-md bg-surface-2 text-[10px] font-bold text-text-3">
                    {i + 1}
                  </span>
                  <code className="truncate text-xs font-mono text-text-1">{row.exception_type}</code>
                </div>
                <span
                  className="ml-4 shrink-0 rounded-full px-2.5 py-0.5 text-xs font-bold text-white"
                  style={{ background: 'var(--gradient-accent)' }}
                >
                  {row.count}
                </span>
              </div>
            ))}
          </div>
        </Card>
      ) : (
        <EmptyState title="No data yet" description="Metrics populate once incidents are ingested." />
      )}
    </div>
  )
}

function ChartCard({
  title,
  subtitle,
  children,
}: {
  title: string
  subtitle?: string
  children: React.ReactNode
}) {
  return (
    <Card className="overflow-hidden">
      <div className="border-b border-border px-6 py-4">
        <h2 className="text-[13px] font-semibold text-text-1">{title}</h2>
        {subtitle && <p className="mt-0.5 text-xs text-text-3">{subtitle}</p>}
      </div>
      <div className="px-3 py-5">{children}</div>
    </Card>
  )
}
