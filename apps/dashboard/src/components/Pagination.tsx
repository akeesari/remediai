interface Props {
  page: number
  pages: number
  total: number
  onPage: (p: number) => void
}

export function Pagination({ page, pages, total, onPage }: Props) {
  if (pages <= 1) return null

  return (
    <div className="flex flex-wrap items-center justify-between gap-3 px-5 py-3.5">
      <p className="text-xs font-medium text-text-3">
        Page <span className="text-text-2">{page}</span> of{' '}
        <span className="text-text-2">{pages}</span> &mdash;{' '}
        <span className="text-text-2">{total.toLocaleString()}</span> total
      </p>
      <div className="flex items-center gap-1.5">
        <button
          onClick={() => onPage(page - 1)}
          disabled={page <= 1}
          className="rounded-lg border border-border bg-surface px-3.5 py-1.5 text-xs font-medium text-text-2 shadow-xs transition-all hover:bg-surface-2 hover:text-text-1 hover:shadow-sm disabled:cursor-not-allowed disabled:opacity-40"
        >
          ← Previous
        </button>
        <button
          onClick={() => onPage(page + 1)}
          disabled={page >= pages}
          className="rounded-lg border border-border bg-surface px-3.5 py-1.5 text-xs font-medium text-text-2 shadow-xs transition-all hover:bg-surface-2 hover:text-text-1 hover:shadow-sm disabled:cursor-not-allowed disabled:opacity-40"
        >
          Next →
        </button>
      </div>
    </div>
  )
}
