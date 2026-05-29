import { clsx } from 'clsx'

type Variant = 'primary' | 'ghost' | 'outline' | 'destructive'
type Size = 'sm' | 'md' | 'lg'

interface ButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: Variant
  size?: Size
}

export function Button({ variant = 'ghost', size = 'md', className, children, ...rest }: ButtonProps) {
  return (
    <button
      className={clsx(
        'inline-flex items-center justify-center gap-2 rounded-lg font-medium',
        'transition-all duration-150 select-none',
        'disabled:cursor-not-allowed disabled:opacity-50',
        'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent/60 focus-visible:ring-offset-2',

        size === 'sm' && 'h-8 px-3 text-xs',
        size === 'md' && 'h-9 px-4 text-sm',
        size === 'lg' && 'h-11 px-6 text-[15px]',

        variant === 'primary' && [
          'text-white shadow-sm',
          'active:scale-[0.98]',
        ],
        variant === 'ghost' && [
          'bg-transparent text-text-2',
          'hover:bg-surface-2 hover:text-text-1',
        ],
        variant === 'outline' && [
          'border border-border bg-surface text-text-1 shadow-xs',
          'hover:bg-surface-2 hover:border-border-2 hover:shadow-sm',
        ],
        variant === 'destructive' && [
          'text-error border shadow-xs',
          'hover:bg-surface-2',
        ],
        className,
      )}
      style={
        variant === 'primary'
          ? { background: 'var(--gradient-accent)', borderColor: 'transparent' }
          : variant === 'destructive'
          ? { borderColor: 'var(--color-error)', backgroundColor: 'var(--color-error-muted)' }
          : undefined
      }
      {...rest}
    >
      {children}
    </button>
  )
}
