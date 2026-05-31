import { clsx } from 'clsx'

interface SkeletonBlockProps {
  className?: string
  rounded?: 'sm' | 'md' | 'lg' | 'full'
}

export function SkeletonBlock({ className, rounded = 'md' }: SkeletonBlockProps) {
  return (
    <div
      className={clsx(
        'skeleton-shimmer',
        rounded === 'sm'   && 'rounded-sm',
        rounded === 'md'   && 'rounded-md',
        rounded === 'lg'   && 'rounded-lg',
        rounded === 'full' && 'rounded-full',
        className,
      )}
    />
  )
}
