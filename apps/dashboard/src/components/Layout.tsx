import { NavLink, Outlet } from 'react-router-dom'
import { useEffect, useMemo, useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { clsx } from 'clsx'
import { getIntegrationsHealth } from '../api/integrations'

const NAV = [
  { to: '/incidents', label: 'Incidents' },
  { to: '/targets', label: 'Targets' },
  { to: '/metrics', label: 'Metrics' },
  { to: '/logs', label: 'Logs' },
]

const BANNER_DISMISS_KEY = 'remediai.integrationWarnings.dismissed'

export function Layout() {
  const { data: integrations } = useQuery({
    queryKey: ['integrations-health'],
    queryFn: getIntegrationsHealth,
  })

  const warningText = useMemo(() => integrations?.warnings.join(' ') ?? '', [integrations])
  const [dismissedWarning, setDismissedWarning] = useState<string>('')

  useEffect(() => {
    setDismissedWarning(localStorage.getItem(BANNER_DISMISS_KEY) ?? '')
  }, [])

  const showWarningBanner = Boolean(
    warningText && warningText.length > 0 && warningText !== dismissedWarning,
  )

  function dismissWarnings(): void {
    if (!warningText) {
      return
    }
    localStorage.setItem(BANNER_DISMISS_KEY, warningText)
    setDismissedWarning(warningText)
  }

  const badges = [
    { label: 'LLM', value: integrations?.llm_provider_id },
    { label: 'Retrieval', value: integrations?.retrieval_provider_id },
    { label: 'SCM', value: integrations?.scm.provider_id },
    { label: 'Ticketing', value: integrations?.ticketing.provider_id },
  ]

  return (
    <div className="min-h-screen bg-gray-50">
      <nav className="border-b border-gray-200 bg-white">
        <div className="mx-auto flex max-w-7xl items-center gap-8 px-4 py-3">
          <span className="text-lg font-bold text-indigo-700">RemediAI</span>
          {NAV.map(({ to, label }) => (
            <NavLink
              key={to}
              to={to}
              className={({ isActive }) =>
                clsx(
                  'text-sm font-medium transition-colors',
                  isActive ? 'text-indigo-700' : 'text-gray-500 hover:text-gray-900',
                )
              }
            >
              {label}
            </NavLink>
          ))}
          <div className="ml-auto flex items-center gap-2">
            {badges.map((badge) => (
              <span
                key={badge.label}
                className="rounded-full border border-gray-200 bg-gray-50 px-2 py-0.5 text-xs text-gray-600"
              >
                {badge.label}: {badge.value ?? 'n/a'}
              </span>
            ))}
          </div>
        </div>
      </nav>
      {showWarningBanner && (
        <div className="border-b border-amber-200 bg-amber-50">
          <div className="mx-auto flex max-w-7xl items-center gap-4 px-4 py-2 text-sm text-amber-800">
            <span className="flex-1">{warningText}</span>
            <NavLink to="/logs" className="text-amber-900 underline hover:text-amber-950">
              View logs
            </NavLink>
            <NavLink to="/targets" className="text-amber-900 underline hover:text-amber-950">
              Configure targets
            </NavLink>
            <button
              onClick={dismissWarnings}
              className="rounded border border-amber-300 bg-amber-100 px-2 py-0.5 text-xs text-amber-900"
            >
              Dismiss
            </button>
          </div>
        </div>
      )}
      <main className="mx-auto max-w-7xl px-4 py-6">
        <Outlet />
      </main>
    </div>
  )
}
