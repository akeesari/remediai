interface Props {
  error: Error
  resetErrorBoundary: () => void
}

export function AppErrorFallback({ error, resetErrorBoundary }: Props) {
  return (
    <div className="flex flex-col items-center justify-center min-h-screen p-8">
      <h1 className="text-2xl font-bold text-red-600 mb-4">Something went wrong</h1>
      <pre className="text-sm text-gray-700 bg-gray-100 rounded p-4 max-w-xl overflow-auto mb-6 whitespace-pre-wrap">
        {error.message}
      </pre>
      <button
        onClick={resetErrorBoundary}
        className="px-4 py-2 bg-blue-600 text-white rounded hover:bg-blue-700"
      >
        Try again
      </button>
    </div>
  )
}
