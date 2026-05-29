import { useEffect, useState } from 'react'
import { Sidebar } from './Sidebar'
import { BottomTabBar } from './BottomTabBar'
import { TopBar } from './TopBar'

const STORAGE_KEY = 'remediai.sidebar.collapsed'

export function AppShell({ children }: { children: React.ReactNode }) {
  const [collapsed, setCollapsed] = useState(false)

  useEffect(() => {
    const persisted = localStorage.getItem(STORAGE_KEY)
    if (persisted !== null) {
      setCollapsed(persisted === 'true')
      return
    }
    const desktopSm = window.matchMedia('(min-width: 1024px) and (max-width: 1279px)')
    if (desktopSm.matches) setCollapsed(true)
  }, [])

  useEffect(() => {
    localStorage.setItem(STORAGE_KEY, String(collapsed))
  }, [collapsed])

  const sidebarW = collapsed ? 64 : 240

  return (
    <div className="min-h-screen bg-bg text-text-1">
      {/* ── Fixed sidebar (desktop only) ── */}
      <Sidebar
        collapsed={collapsed}
        onToggle={() => setCollapsed((v) => !v)}
        width={sidebarW}
      />

      {/* ── Main content — offset by sidebar width on lg+ ── */}
      <div
        className="min-h-screen transition-[padding-left] duration-[220ms] ease-spring pl-0 lg:pl-[var(--sidebar-width)]"
        style={{
          ['--sidebar-width' as any]: `${sidebarW}px`,
        }}
      >
        {/* Show padding only on desktop, zero on mobile */}
        <div className="lg:hidden" style={{ paddingLeft: 0 }}>
          {/* TopBar visible only on mobile */}
        </div>
        <TopBar />
        <main className="mx-auto max-w-[1320px] px-5 pb-[calc(5.5rem+env(safe-area-inset-bottom))] pt-7 sm:px-8 lg:pb-10 lg:pt-8">
          {children}
        </main>
      </div>

      <BottomTabBar />
    </div>
  )
}
