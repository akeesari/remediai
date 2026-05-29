import { ChevronLeft } from 'lucide-react'
import { clsx } from 'clsx'
import { NAV_ROUTES } from './nav'
import { NavItem } from './NavItem'
import { ThemeToggle } from '../ui/ThemeToggle'

interface SidebarProps {
  collapsed: boolean
  onToggle: () => void
  width: number
}

export function Sidebar({ collapsed, onToggle, width }: SidebarProps) {
  return (
    <aside
      className="fixed top-0 left-0 z-30 hidden h-screen flex-col lg:flex"
      style={{
        width,
        backgroundColor: 'var(--sidebar-bg)',
        borderRight: '1px solid var(--sidebar-border)',
        boxShadow: 'var(--shadow-sm)',
        transition: 'width 220ms cubic-bezier(0.16,1,0.3,1)',
        overflow: 'hidden',
      }}
    >
      {/* ── Logo ── */}
      <div
        className={clsx(
          'flex h-[60px] shrink-0 items-center border-b',
          collapsed ? 'justify-center px-3' : 'gap-3 px-5',
        )}
        style={{ borderBottomColor: 'var(--sidebar-border)' }}
      >
        {/* Brand icon — gradient pill */}
        <span
          className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg text-white text-sm font-black tracking-tight shadow-sm"
          style={{ background: 'var(--gradient-accent)' }}
        >
          R
        </span>
        {!collapsed && (
          <div className="min-w-0 overflow-hidden">
            <p
              className="truncate text-[13px] font-bold tracking-[-0.02em] text-text-1"
              style={{ letterSpacing: '-0.02em' }}
            >
              RemediAI
            </p>
            <p className="truncate text-[10px] font-medium uppercase tracking-[0.08em] text-text-3">
              AI Ops Platform
            </p>
          </div>
        )}
      </div>

      {/* ── Navigation ── */}
      <nav className="flex-1 overflow-hidden p-2.5">
        <div className="space-y-0.5">
          {NAV_ROUTES.map((route) => (
            <NavItem key={route.to} route={route} compact={collapsed} />
          ))}
        </div>
      </nav>

      {/* ── Bottom controls ── */}
      <div
        className="shrink-0 space-y-1.5 border-t p-2.5"
        style={{ borderTopColor: 'var(--sidebar-border)' }}
      >
        {/* Theme toggle */}
        <div className={clsx('flex', collapsed ? 'justify-center' : '')}>
          <ThemeToggle compact={collapsed} className={collapsed ? undefined : 'w-full'} />
        </div>

        {/* Collapse button */}
        <button
          type="button"
          onClick={onToggle}
          title={collapsed ? 'Expand sidebar' : 'Collapse sidebar'}
          className={clsx(
            'flex h-9 w-full items-center rounded-lg text-xs font-medium text-text-3',
            'border border-transparent transition-all duration-150',
            'hover:border-border hover:bg-surface-2 hover:text-text-2',
            collapsed ? 'justify-center px-2' : 'justify-between px-3',
          )}
        >
          {!collapsed && <span>Collapse</span>}
          <ChevronLeft
            className={clsx(
              'h-3.5 w-3.5 shrink-0 transition-transform duration-[220ms]',
              collapsed && 'rotate-180',
            )}
          />
        </button>
      </div>
    </aside>
  )
}
