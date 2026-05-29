import { NavLink } from 'react-router-dom'
import { clsx } from 'clsx'
import * as Tooltip from '@radix-ui/react-tooltip'
import type { NavRoute } from './nav'

interface NavItemProps {
  route: NavRoute
  compact?: boolean
}

export function NavItem({ route, compact = false }: NavItemProps) {
  const Icon = route.icon

  const content = ({ isActive }: { isActive: boolean }) => (
    <span
      className={clsx(
        'relative flex h-9 w-full items-center rounded-lg text-[13px] font-medium',
        'transition-all duration-150',
        compact ? 'justify-center px-2' : 'gap-3 px-3',
        isActive
          ? 'text-accent'
          : 'text-text-2 hover:bg-surface-2 hover:text-text-1',
      )}
      style={
        isActive
          ? { backgroundColor: 'var(--color-accent-muted)' }
          : undefined
      }
    >
      {/* Active left-bar */}
      {isActive && !compact && (
        <span
          className="absolute left-0 top-2 bottom-2 w-0.5 rounded-full"
          style={{ backgroundColor: 'var(--color-accent)' }}
          aria-hidden="true"
        />
      )}
      <Icon
        className={clsx('h-[18px] w-[18px] shrink-0')}
        strokeWidth={isActive ? 2.5 : 1.75}
        style={{ color: isActive ? 'var(--color-accent)' : undefined }}
      />
      {!compact && (
        <span className="truncate">{route.label}</span>
      )}
    </span>
  )

  if (!compact) {
    return <NavLink to={route.to}>{content}</NavLink>
  }

  return (
    <Tooltip.Provider delayDuration={80}>
      <Tooltip.Root>
        <Tooltip.Trigger asChild>
          <NavLink to={route.to}>{content}</NavLink>
        </Tooltip.Trigger>
        <Tooltip.Portal>
          <Tooltip.Content
            side="right"
            sideOffset={10}
            className={clsx(
              'z-50 rounded-lg px-3 py-1.5 text-xs font-semibold shadow-md',
              'border border-border bg-surface text-text-1',
              'animate-in fade-in-0 zoom-in-95 data-[state=closed]:animate-out data-[state=closed]:fade-out-0',
            )}
          >
            {route.label}
            <Tooltip.Arrow className="fill-surface" />
          </Tooltip.Content>
        </Tooltip.Portal>
      </Tooltip.Root>
    </Tooltip.Provider>
  )
}
