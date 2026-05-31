import { Sun, Moon } from 'lucide-react'
import { clsx } from 'clsx'
import { useTheme } from '../shell/ThemeContext'

interface ThemeToggleProps {
  compact?: boolean
  className?: string
}

export function ThemeToggle({ compact = false, className }: ThemeToggleProps) {
  const { theme, toggleTheme } = useTheme()
  const isDark = theme === 'dark'

  if (compact) {
    return (
      <button
        type="button"
        id="theme-toggle"
        onClick={toggleTheme}
        aria-label={isDark ? 'Switch to light mode' : 'Switch to dark mode'}
        title={isDark ? 'Light mode' : 'Dark mode'}
        className={clsx(
          'flex h-8 w-8 items-center justify-center rounded-lg border border-border',
          'transition-all duration-150 hover:bg-surface-2',
          className,
        )}
      >
        {isDark
          ? <Moon className="h-3.5 w-3.5 text-accent" />
          : <Sun className="h-3.5 w-3.5 text-warning" />
        }
      </button>
    )
  }

  return (
    <button
      type="button"
      id="theme-toggle-sidebar"
      onClick={toggleTheme}
      role="switch"
      aria-checked={isDark}
      aria-label={isDark ? 'Switch to light mode' : 'Switch to dark mode'}
      className={clsx(
        'flex h-9 w-full items-center gap-2.5 rounded-lg border border-border px-3',
        'text-xs font-medium text-text-2 transition-all duration-150',
        'hover:border-border-2 hover:bg-surface-2 hover:text-text-1',
        className,
      )}
    >
      {isDark
        ? <Moon className="h-3.5 w-3.5 shrink-0 text-accent" />
        : <Sun className="h-3.5 w-3.5 shrink-0 text-warning" />
      }
      <span className="flex-1 text-left">{isDark ? 'Dark mode' : 'Light mode'}</span>
      {/* Toggle pill */}
      <span
        className="relative flex h-5 w-9 shrink-0 rounded-full transition-colors duration-200"
        style={{
          backgroundColor: isDark ? 'var(--color-accent)' : 'var(--color-surface-3)',
        }}
      >
        <span
          className="absolute top-0.5 h-4 w-4 rounded-full bg-white shadow transition-transform duration-200"
          style={{ transform: isDark ? 'translateX(16px)' : 'translateX(2px)' }}
        />
      </span>
    </button>
  )
}
