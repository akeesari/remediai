import { NavLink, Outlet } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { clsx } from 'clsx'
import { getIntegrationsHealth } from '../api/integrations'

const NAV = [
  { to: '/incidents', label: 'Incidents' },
  { to: '/metrics', label: 'Metrics' },
  { to: '/logs', label: 'Logs' },
]

export function Layout() {
  const { data: integrations } = useQuery({
    queryKey: ['integrations-health'],
    queryFn: getIntegrationsHealth,
  })

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
        </div>
      </nav>
      {integrations && integrations.warnings.length > 0 && (
        <div className="border-b border-amber-200 bg-amber-50">
          <div className="mx-auto max-w-7xl px-4 py-2 text-sm text-amber-800">
            {integrations.warnings.join(' ')}
          </div>
        </div>
      )}
      <main className="mx-auto max-w-7xl px-4 py-6">
        <Outlet />
      </main>
    </div>
  )
}
