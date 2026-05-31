// Inline CSS-variable approach — no Tailwind colour classes needed (theme-safe for both light/dark)

type Variant =
  | 'priority-critical'
  | 'priority-high'
  | 'priority-medium'
  | 'priority-low'
  | 'status-new'
  | 'status-triaged'
  | 'status-analyzed'
  | 'status-resolved'
  | 'status-ignored'
  | 'status-default'

const BADGE_CSS: Record<Variant, { bg: string; text: string; ring: string }> = {
  'priority-critical': { bg: 'rgba(220,38,38,0.10)',  text: 'var(--color-critical)', ring: 'rgba(220,38,38,0.25)' },
  'priority-high':     { bg: 'rgba(234,88,12,0.10)',  text: 'var(--color-high)',     ring: 'rgba(234,88,12,0.25)' },
  'priority-medium':   { bg: 'rgba(202,138,4,0.10)',  text: 'var(--color-medium)',   ring: 'rgba(202,138,4,0.25)' },
  'priority-low':      { bg: 'rgba(21,128,61,0.10)',  text: 'var(--color-low)',      ring: 'rgba(21,128,61,0.25)' },
  'status-new':        { bg: 'rgba(37,99,235,0.10)',  text: '#2563eb',               ring: 'rgba(37,99,235,0.20)' },
  'status-triaged':    { bg: 'rgba(124,58,237,0.10)', text: '#7c3aed',               ring: 'rgba(124,58,237,0.20)' },
  'status-analyzed':   { bg: 'rgba(8,145,178,0.10)',  text: '#0891b2',               ring: 'rgba(8,145,178,0.20)' },
  'status-resolved':   { bg: 'rgba(21,128,61,0.10)',  text: 'var(--color-success)',  ring: 'rgba(21,128,61,0.20)' },
  'status-ignored':    { bg: 'var(--color-surface-2)',text: 'var(--color-text-2)',   ring: 'var(--color-border)' },
  'status-default':    { bg: 'var(--color-surface-2)',text: 'var(--color-text-2)',   ring: 'var(--color-border)' },
}

interface BadgeProps {
  text: string
  variant: Variant
  dot?: boolean
}

export function Badge({ text, variant, dot }: BadgeProps) {
  const css = BADGE_CSS[variant]
  return (
    <span
      style={{
        backgroundColor: css.bg,
        color: css.text,
        boxShadow: `0 0 0 1px ${css.ring}`,
      }}
      className="inline-flex items-center gap-1.5 rounded-full px-2.5 py-0.5 text-xs font-semibold capitalize leading-5"
    >
      {dot && (
        <span
          className="h-1.5 w-1.5 rounded-full flex-shrink-0"
          style={{ backgroundColor: css.text }}
          aria-hidden="true"
        />
      )}
      {text}
    </span>
  )
}

export function priorityVariant(priority: string): Variant {
  switch (priority.toLowerCase()) {
    case 'critical': return 'priority-critical'
    case 'high':     return 'priority-high'
    case 'medium':   return 'priority-medium'
    case 'low':      return 'priority-low'
    default:         return 'priority-low'
  }
}

export function statusVariant(status: string): Variant {
  switch (status.toLowerCase()) {
    case 'new':      return 'status-new'
    case 'triaged':  return 'status-triaged'
    case 'analyzed': return 'status-analyzed'
    case 'resolved': return 'status-resolved'
    case 'ignored':  return 'status-ignored'
    default:         return 'status-default'
  }
}
