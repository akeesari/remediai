import { clsx } from 'clsx'

interface DataTableProps {
  columns: string[]
  children: React.ReactNode
  className?: string
}

export function DataTable({ columns, children, className }: DataTableProps) {
  return (
    <div
      className={clsx(
        'overflow-hidden rounded-lg border border-border bg-surface shadow-sm',
        className,
      )}
    >
      <div className="overflow-x-auto">
        <table className="min-w-full divide-y divide-border text-sm">
          <thead className="bg-surface-2">
            <tr>
              {columns.map((col) => (
                <th
                  key={col}
                  className="px-4 py-3 text-left text-xs font-semibold uppercase tracking-widest text-text-2"
                >
                  {col}
                </th>
              ))}
            </tr>
          </thead>
          <tbody className="divide-y divide-border bg-surface">{children}</tbody>
        </table>
      </div>
    </div>
  )
}
