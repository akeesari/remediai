interface ToastProps {
  kind: 'success' | 'warning' | 'error'
  text: string
  onClose: () => void
}

export function Toast({ kind, text, onClose }: ToastProps) {
  const palette =
    kind === 'success'
      ? 'border-emerald-800/60 bg-emerald-950/90 text-emerald-200'
      : kind === 'warning'
        ? 'border-amber-800/60 bg-amber-950/90 text-amber-200'
        : 'border-red-800/60 bg-red-950/90 text-red-200'

  return (
    <div className={`pointer-events-auto flex items-start justify-between gap-3 rounded-lg border px-3 py-2 text-sm shadow-md ${palette}`}>
      <span>{text}</span>
      <button type="button" onClick={onClose} className="shrink-0 text-xs opacity-80 hover:opacity-100">
        Dismiss
      </button>
    </div>
  )
}
