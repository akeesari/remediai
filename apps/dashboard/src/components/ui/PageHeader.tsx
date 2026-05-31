interface PageHeaderProps {
  title: string
  subtitle?: string
  actions?: React.ReactNode
  eyebrow?: string
}

export function PageHeader({ title, subtitle, actions, eyebrow }: PageHeaderProps) {
  return (
    <header className="mb-7 flex flex-wrap items-start justify-between gap-4">
      <div>
        {eyebrow && (
          <p
            className="mb-1.5 text-[11px] font-semibold uppercase tracking-[0.1em]"
            style={{ color: 'var(--color-accent)' }}
          >
            {eyebrow}
          </p>
        )}
        <h1
          className="font-black tracking-tight text-text-1"
          style={{ fontSize: 'clamp(1.5rem, 3vw, 2rem)', letterSpacing: '-0.03em', lineHeight: 1.15 }}
        >
          {title}
        </h1>
        {subtitle && (
          <p className="mt-2 max-w-2xl text-sm leading-relaxed text-text-2">
            {subtitle}
          </p>
        )}
      </div>
      {actions && (
        <div className="flex flex-wrap items-center gap-2 shrink-0">{actions}</div>
      )}
    </header>
  )
}
