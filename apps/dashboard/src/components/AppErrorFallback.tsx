interface Props {
  error: Error
  resetErrorBoundary: () => void
}

export function AppErrorFallback({ error, resetErrorBoundary }: Props) {
  return (
    <div className="flex min-h-screen flex-col items-center justify-center bg-bg p-8 text-center">
      <h1 className="mb-4 text-2xl font-semibold text-error">Something went wrong</h1>
      <pre className="mb-6 max-w-xl overflow-auto rounded-lg border border-border bg-surface p-4 text-sm text-text-2 whitespace-pre-wrap">
        {error.message}
      </pre>
      <button
        onClick={resetErrorBoundary}
        className="rounded-md border border-accent bg-accent px-4 py-2 text-sm font-medium text-text-1 transition-colors hover:border-accent-hover hover:bg-accent-hover"
      >
        Try again
      </button>
    </div>
  )
}
