import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { useNavigate } from 'react-router-dom'
import { listIncidents } from '../api/incidents'
import { PriorityBadge } from '../components/PriorityBadge'
import { StatusBadge } from '../components/StatusBadge'
import { Pagination } from '../components/Pagination'

const PRIORITIES = ['', 'critical', 'high', 'medium', 'low']
const STATUSES = ['', 'new', 'triaged', 'analyzed', 'resolved', 'ignored']

export function IncidentList() {
  const navigate = useNavigate()
  const [page, setPage] = useState(1)
  const [priority, setPriority] = useState('')
  const [status, setStatus] = useState('')

  const { data, isLoading, isError } = useQuery({
    queryKey: ['incidents', page, priority, status],
    queryFn: () =>
      listIncidents({
        page,
        page_size: 20,
        priority: priority || undefined,
        status: status || undefined,
      }),
  })

  function handleFilterChange(setter: (v: string) => void) {
    return (e: React.ChangeEvent<HTMLSelectElement>) => {
      setter(e.target.value)
      setPage(1)
    }
  }

  return (
    <div>
      <div className="mb-4 flex items-center justify-between">
        <h1 className="text-xl font-semibold text-gray-900">Incidents</h1>
        <div className="flex gap-3">
          <select
            value={priority}
            onChange={handleFilterChange(setPriority)}
            className="rounded border border-gray-300 px-3 py-1.5 text-sm"
          >
            {PRIORITIES.map((p) => (
              <option key={p} value={p}>
                {p === '' ? 'All priorities' : p}
              </option>
            ))}
          </select>
          <select
            value={status}
            onChange={handleFilterChange(setStatus)}
            className="rounded border border-gray-300 px-3 py-1.5 text-sm"
          >
            {STATUSES.map((s) => (
              <option key={s} value={s}>
                {s === '' ? 'All statuses' : s}
              </option>
            ))}
          </select>
        </div>
      </div>

      <div className="overflow-hidden rounded-lg border border-gray-200 bg-white shadow-sm">
        {isLoading && (
          <p className="px-6 py-8 text-center text-sm text-gray-500">Loading…</p>
        )}
        {isError && (
          <p className="px-6 py-8 text-center text-sm text-red-600">Failed to load incidents.</p>
        )}
        {data && (
          <>
            <table className="min-w-full divide-y divide-gray-200 text-sm">
              <thead className="bg-gray-50 text-left text-xs font-medium uppercase tracking-wide text-gray-500">
                <tr>
                  <th className="px-4 py-3">Exception</th>
                  <th className="px-4 py-3">Message</th>
                  <th className="px-4 py-3">Priority</th>
                  <th className="px-4 py-3">Status</th>
                  <th className="px-4 py-3">Created</th>
                  <th className="px-4 py-3">External Item</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-100">
                {data.items.length === 0 && (
                  <tr>
                    <td colSpan={6} className="px-4 py-6 text-center text-gray-400">
                      No incidents found.
                    </td>
                  </tr>
                )}
                {data.items.map((inc) => (
                  <tr
                    key={inc.id}
                    onClick={() => navigate(`/incidents/${inc.id}`)}
                    className="cursor-pointer hover:bg-indigo-50 transition-colors"
                  >
                    <td className="px-4 py-3 font-mono text-xs text-gray-800 max-w-xs truncate">
                      {inc.exception_type.split('.').pop()}
                    </td>
                    <td className="px-4 py-3 text-gray-600 max-w-sm truncate">
                      {inc.exception_message}
                    </td>
                    <td className="px-4 py-3">
                      <PriorityBadge priority={inc.priority} />
                    </td>
                    <td className="px-4 py-3">
                      <StatusBadge status={inc.status} />
                    </td>
                    <td className="px-4 py-3 text-gray-500 whitespace-nowrap">
                      {new Date(inc.created_at).toLocaleString()}
                    </td>
                    <td className="px-4 py-3">
                      {inc.external_item_url ? (
                        <a
                          href={inc.external_item_url}
                          target="_blank"
                          rel="noreferrer"
                          onClick={(e) => e.stopPropagation()}
                          className="text-indigo-600 hover:underline"
                        >
                          View
                        </a>
                      ) : (
                        <span className="text-gray-300">—</span>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
            <Pagination
              page={data.page}
              pages={data.pages}
              total={data.total}
              onPage={setPage}
            />
          </>
        )}
      </div>
    </div>
  )
}
