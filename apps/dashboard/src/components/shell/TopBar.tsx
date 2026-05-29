import { ChevronLeft } from 'lucide-react'
import { useLocation, useNavigate } from 'react-router-dom'
import { ThemeToggle } from '../ui/ThemeToggle'

const TITLES: Array<{ test: (p: string) => boolean; title: string }> = [
  { test: (p) => p === '/incidents',          title: 'Incidents' },
  { test: (p) => p.startsWith('/incidents/'), title: 'Incident Detail' },
  { test: (p) => p === '/metrics',             title: 'Metrics' },
  { test: (p) => p === '/targets',             title: 'Targets' },
  { test: (p) => p === '/logs',                title: 'Container Logs' },
]

export function TopBar() {
  const navigate = useNavigate()
  const { pathname } = useLocation()
  const title = TITLES.find((e) => e.test(pathname))?.title ?? 'Dashboard'
  const showBack = pathname.startsWith('/incidents/')

  return (
    <header
      className="sticky top-0 z-20 flex h-[56px] items-center justify-between px-5 lg:hidden"
      style={{
        backgroundColor: 'color-mix(in srgb, var(--color-surface) 85%, transparent)',
        backdropFilter: 'blur(12px) saturate(180%)',
        borderBottom: '1px solid var(--color-border)',
      }}
    >
      <div className="flex items-center gap-2.5">
        {showBack ? (
          <>
            <button
              type="button"
              onClick={() => navigate(-1)}
              className="flex h-8 w-8 items-center justify-center rounded-lg border border-border text-text-2 hover:bg-surface-2 hover:text-text-1 transition-colors"
              aria-label="Go back"
            >
              <ChevronLeft className="h-4 w-4" />
            </button>
            <p className="font-bold text-[13px] tracking-tight text-text-1">
              {title}
            </p>
          </>
        ) : (
          <div className="flex items-center gap-2">
            <span
              className="flex h-7 w-7 items-center justify-center rounded-md text-white text-xs font-black tracking-tight"
              style={{ background: 'var(--gradient-accent)' }}
            >
              R
            </span>
            <span className="text-[14px] font-black tracking-tight text-text-1">
              RemediAI
            </span>
          </div>
        )}
      </div>
      <ThemeToggle compact />
    </header>
  )
}
