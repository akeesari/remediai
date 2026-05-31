import type { LucideIcon } from 'lucide-react'

type GradientKey = 'accent' | 'success' | 'warning' | 'error' | 'blue'

const GLOW_COLORS: Record<GradientKey, { start: string; end: string; textAccent: string; bgAccent: string }> = {
  accent: {
    start: 'rgba(59, 130, 246, 0.15)',
    end: 'rgba(96, 165, 250, 0.15)',
    textAccent: 'var(--color-accent)',
    bgAccent: 'var(--color-accent-muted)',
  },
  success: {
    start: 'rgba(16, 185, 129, 0.15)',
    end: 'rgba(20, 184, 166, 0.15)',
    textAccent: 'var(--color-success)',
    bgAccent: 'var(--color-success-muted)',
  },
  warning: {
    start: 'rgba(245, 158, 11, 0.15)',
    end: 'rgba(234, 179, 8, 0.15)',
    textAccent: 'var(--color-warning)',
    bgAccent: 'var(--color-warning-muted)',
  },
  error: {
    start: 'rgba(239, 68, 68, 0.15)',
    end: 'rgba(244, 63, 94, 0.15)',
    textAccent: 'var(--color-error)',
    bgAccent: 'var(--color-error-muted)',
  },
  blue: {
    start: 'rgba(59, 130, 246, 0.15)',
    end: 'rgba(14, 165, 233, 0.15)',
    textAccent: '#3b82f6',
    bgAccent: 'rgba(59, 130, 246, 0.08)',
  },
}

interface StatCardProps {
  label: string
  value: number | string
  icon?: LucideIcon
  gradient?: GradientKey
  description?: string
}

export function StatCard({ label, value, icon: Icon, gradient = 'accent', description }: StatCardProps) {
  const glow = GLOW_COLORS[gradient]

  return (
    <div
      className="relative overflow-hidden rounded-xl border border-border p-6 shadow-sm transition-all duration-300 hover:shadow-md hover:-translate-y-[1px]"
      style={{
        background: `radial-gradient(circle at 0% 0%, ${glow.start} 0%, transparent 60%), radial-gradient(circle at 100% 100%, ${glow.end} 0%, transparent 60%), var(--color-surface)`,
      }}
    >
      {/* Subtle noise overlay for texture */}
      <div
        className="pointer-events-none absolute inset-0 opacity-[0.015] dark:opacity-[0.03]"
        style={{
          backgroundImage: `url("data:image/svg+xml,%3Csvg viewBox='0 0 200 200' xmlns='http://www.w3.org/2000/svg'%3E%3Cfilter id='n'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='0.9' numOctaves='4'/%3E%3C/filter%3E%3Crect width='100%25' height='100%25' filter='url(%23n)'/%3E%3C/svg%3E")`,
          backgroundSize: '200px 200px',
        }}
      />

      {/* Content */}
      <div className="relative flex items-start justify-between gap-3">
        <div>
          <p className="text-[11px] font-semibold uppercase tracking-[0.1em] text-text-2">
            {label}
          </p>
          <p
            className="mt-2 font-black tracking-tight text-text-1"
            style={{ fontSize: 'clamp(2rem, 4vw, 2.75rem)', lineHeight: 1.05, letterSpacing: '-0.03em' }}
          >
            {value}
          </p>
          {description && (
            <p className="mt-1.5 text-xs font-medium text-text-3">{description}</p>
          )}
        </div>
        {Icon && (
          <span
            className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl"
            style={{
              backgroundColor: glow.bgAccent,
              border: '1px solid var(--color-border)',
            }}
          >
            <Icon className="h-5 w-5" style={{ color: glow.textAccent }} strokeWidth={2} />
          </span>
        )}
      </div>
    </div>
  )
}

/** Simpler outlined stat for secondary metrics */
export function StatCardOutlined({
  label,
  value,
  description,
}: {
  label: string
  value: string | number
  description?: string
}) {
  return (
    <div className="rounded-xl border border-border bg-surface p-5 shadow-sm">
      <p className="text-[11px] font-semibold uppercase tracking-[0.09em] text-text-3">{label}</p>
      <p
        className="mt-2 font-black tracking-tight text-text-1"
        style={{ fontSize: 'clamp(1.75rem, 3vw, 2.25rem)', lineHeight: 1.1, letterSpacing: '-0.02em' }}
      >
        {value}
      </p>
      {description && (
        <p className="mt-1 text-xs text-text-2">{description}</p>
      )}
    </div>
  )
}
