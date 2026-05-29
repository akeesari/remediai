import { NavLink } from 'react-router-dom'
import { clsx } from 'clsx'
import { NAV_ROUTES } from './nav'

export function BottomTabBar() {
  return (
    <nav className="fixed inset-x-0 bottom-0 z-50 border-t border-border bg-surface/90 px-1 pb-[max(env(safe-area-inset-bottom),0.5rem)] pt-1 backdrop-blur lg:hidden">
      <ul className="mx-auto grid max-w-lg grid-cols-4">
        {NAV_ROUTES.map((route) => {
          const Icon = route.icon
          return (
            <li key={route.to}>
              <NavLink
                to={route.to}
                className={({ isActive }) =>
                  clsx(
                    'flex h-14 flex-col items-center justify-center gap-1 rounded-md text-xs font-medium transition-colors',
                    isActive ? 'text-accent' : 'text-text-2 hover:text-text-1',
                  )
                }
              >
                <Icon className="h-5 w-5" />
                <span>{route.label}</span>
              </NavLink>
            </li>
          )
        })}
      </ul>
    </nav>
  )
}
