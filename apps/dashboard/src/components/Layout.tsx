import { Outlet } from 'react-router-dom'
import { useEffect, useMemo, useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { AlertTriangle, X } from 'lucide-react'
import { getIntegrationsHealth } from '../api/integrations'
import { AppShell } from './shell/AppShell'
import { Button } from './ui/Button'

const BANNER_DISMISS_KEY = 'remediai.integrationWarnings.dismissed'

const PROVIDER_LABELS: Record<string, string> = {
  llm:       'LLM',
  retrieval: 'Retrieval',
  scm:       'SCM',
  ticketing: 'Ticketing',
}

export function Layout() {
  const { data: integrations } = useQuery({
    queryKey: ['integrations-health'],
    queryFn: getIntegrationsHealth,
  })

  const warningText = useMemo(() => integrations?.warnings.join(' ') ?? '', [integrations])
  const [dismissedWarning, setDismissedWarning] = useState('')

  useEffect(() => {
    setDismissedWarning(localStorage.getItem(BANNER_DISMISS_KEY) ?? '')
  }, [])

  const showWarningBanner = Boolean(
    warningText && warningText.length > 0 && warningText !== dismissedWarning,
  )

  function dismissWarnings() {
    if (!warningText) return
    localStorage.setItem(BANNER_DISMISS_KEY, warningText)
    setDismissedWarning(warningText)
  }

  const badges = [
    { key: 'llm',       value: integrations?.llm_provider_id },
    { key: 'retrieval', value: integrations?.retrieval_provider_id },
    { key: 'scm',       value: integrations?.scm.provider_id },
    { key: 'ticketing', value: integrations?.ticketing.provider_id },
  ]

  return (
    <AppShell>
      <div className="space-y-5 page-enter">
        {/* Integration status bar */}
        <div className="flex flex-wrap items-center gap-2 rounded-xl border border-border bg-surface px-4 py-3 shadow-xs">
          <span className="mr-1 text-[10px] font-semibold uppercase tracking-[0.08em] text-text-3">
            Integrations
          </span>
          {badges.map(({ key, value }) => {
            const active = Boolean(value && value !== 'none')
            return (
              <span
                key={key}
                className="inline-flex items-center gap-1.5 rounded-full border border-border px-2.5 py-1 text-xs font-medium"
              >
                <span
                  className="h-1.5 w-1.5 rounded-full"
                  style={{
                    backgroundColor: active ? 'var(--color-success)' : 'var(--color-text-3)',
                    boxShadow: active ? '0 0 0 2px var(--color-success-muted)' : 'none',
                  }}
                />
                <span className="text-text-2">{PROVIDER_LABELS[key]}:</span>
                <span className="text-text-1">{value ?? 'n/a'}</span>
              </span>
            )
          })}
        </div>

        {/* Warning banner */}
        {showWarningBanner && (
          <div
            className="flex items-start gap-3 rounded-xl border px-4 py-3.5"
            style={{
              borderColor: 'var(--color-warning-muted)',
              backgroundColor: 'var(--color-warning-muted)',
            }}
          >
            <AlertTriangle
              className="mt-0.5 h-4 w-4 shrink-0"
              style={{ color: 'var(--color-warning)' }}
            />
            <p className="flex-1 text-sm leading-relaxed text-text-1">{warningText}</p>
            <Button
              type="button"
              size="sm"
              variant="ghost"
              onClick={dismissWarnings}
              className="shrink-0 -mr-1 text-text-2"
              aria-label="Dismiss"
            >
              <X className="h-3.5 w-3.5" />
            </Button>
          </div>
        )}

        <Outlet />
      </div>
    </AppShell>
  )
}
