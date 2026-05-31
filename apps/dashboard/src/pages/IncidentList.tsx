import { useState, type ChangeEvent } from 'react'
import { useQuery } from '@tanstack/react-query'
import { useNavigate } from 'react-router-dom'
import * as Dialog from '@radix-ui/react-dialog'
import { Filter, X, AlertCircle } from 'lucide-react'
import { listIncidents } from '../api/incidents'
import { Pagination } from '../components/Pagination'
import { Badge, priorityVariant, statusVariant } from '../components/ui/Badge'
import { Button } from '../components/ui/Button'
import { DataTable } from '../components/ui/DataTable'
import { EmptyState } from '../components/ui/EmptyState'
import { PageHeader } from '../components/ui/PageHeader'
import { SkeletonBlock } from '../components/ui/SkeletonBlock'

const PRIORITIES = ['', 'critical', 'high', 'medium', 'low']
const STATUSES = ['', 'new', 'triaged', 'analyzed', 'resolved', 'ignored']

const SELECT_CLS =
  'h-9 rounded-md border border-border bg-surface px-3 text-sm text-text-1 shadow-xs transition-colors focus:outline-none focus:ring-2 focus:ring-accent focus:border-accent hover:border-border-2'

export function IncidentList() {
  const navigate = useNavigate()
  const [page, setPage] = useState(1)
  const [priority, setPriority] = useState('')
  const [status, setStatus] = useState('')
  const [filtersOpen, setFiltersOpen] = useState(false)

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

  function handleFilterChange(setter: (value: string) => void) {
    return (event: ChangeEvent<HTMLSelectElement>) => {
      setter(event.target.value)
      setPage(1)
    }
  }

  const filters = (
    <>
      <select value={priority} onChange={handleFilterChange(setPriority)} className={SELECT_CLS}>
        {PRIORITIES.map((item) => (
          <option key={item} value={item} className="bg-surface text-text-1">
            {item === '' ? 'All priorities' : item}
          </option>
        ))}
      </select>
      <select value={status} onChange={handleFilterChange(setStatus)} className={SELECT_CLS}>
        {STATUSES.map((item) => (
          <option key={item} value={item} className="bg-surface text-text-1">
            {item === '' ? 'All statuses' : item}
          </option>
        ))}
      </select>
    </>
  )

  return (
    <div className="space-y-5">
      <PageHeader
        eyebrow="Operations"
        title="Incidents"
        subtitle="Track, triage, and inspect every exception incident in one place."
        actions={
          <>
            <div className="hidden items-center gap-2 lg:flex">{filters}</div>
            <Dialog.Root open={filtersOpen} onOpenChange={setFiltersOpen}>
              <Dialog.Trigger asChild>
                <Button type="button" variant="outline" size="sm" className="lg:hidden">
                  <Filter className="h-3.5 w-3.5" />
                  Filter
                </Button>
              </Dialog.Trigger>
              <Dialog.Portal>
                <Dialog.Overlay className="fixed inset-0 z-50 bg-black/50 backdrop-blur-sm lg:hidden" />
                <Dialog.Content className="fixed inset-x-3 bottom-3 z-50 rounded-xl border border-border bg-surface p-5 shadow-lg lg:hidden">
                  <div className="mb-4 flex items-center justify-between">
                    <Dialog.Title className="text-base font-semibold text-text-1">Filters</Dialog.Title>
                    <Dialog.Close asChild>
                      <button type="button" className="rounded-md p-1 text-text-2 hover:bg-surface-2 hover:text-text-1" aria-label="Close filters">
                        <X className="h-4 w-4" />
                      </button>
                    </Dialog.Close>
                  </div>
                  <div className="grid grid-cols-1 gap-3">{filters}</div>
                </Dialog.Content>
              </Dialog.Portal>
            </Dialog.Root>
          </>
        }
      />

      {isLoading && <LoadingState />}
      {isError && (
        <EmptyState
          icon={AlertCircle}
          title="Failed to load incidents"
          description="Refresh the page and try again."
        />
      )}

      {data && (
        <>
          {data.items.length === 0 ? (
            <EmptyState
              title="No incidents yet"
              description="Incidents appear here once the log bridge starts forwarding exceptions."
            />
          ) : (
            <>
              {/* Mobile card list */}
              <div className="space-y-3 lg:hidden">
                {data.items.map((incident) => (
                  <button
                    key={incident.id}
                    type="button"
                    onClick={() => navigate(`/incidents/${incident.id}`)}
                    className="group w-full rounded-xl border border-border bg-surface p-4 text-left shadow-xs transition-all duration-150 hover:border-border-2 hover:shadow-sm hover:-translate-y-[1px]"
                  >
                    <p className="font-mono text-xs font-medium text-accent">
                      {incident.exception_type.split('.').pop()}
                    </p>
                    <p className="mt-1.5 line-clamp-2 text-sm leading-relaxed text-text-1">
                      {incident.exception_message}
                    </p>
                    <div className="mt-3 flex flex-wrap items-center gap-2">
                      <Badge dot text={incident.priority} variant={priorityVariant(incident.priority)} />
                      <Badge dot text={incident.status} variant={statusVariant(incident.status)} />
                      <span className="ml-auto text-xs text-text-3">
                        {new Date(incident.created_at).toLocaleString()}
                      </span>
                    </div>
                  </button>
                ))}
              </div>

              {/* Desktop table */}
              <DataTable
                className="hidden lg:block"
                columns={['Exception', 'Message', 'Priority', 'Status', 'Created', 'External']}
              >
                {data.items.map((incident) => (
                  <tr
                    key={incident.id}
                    onClick={() => navigate(`/incidents/${incident.id}`)}
                    className="cursor-pointer transition-colors hover:bg-surface-2"
                  >
                    <td className="px-4 py-3.5 font-mono text-xs font-medium text-accent max-w-xs truncate">
                      {incident.exception_type.split('.').pop()}
                    </td>
                    <td className="max-w-sm truncate px-4 py-3.5 text-sm text-text-1">
                      {incident.exception_message}
                    </td>
                    <td className="px-4 py-3.5">
                      <Badge dot text={incident.priority} variant={priorityVariant(incident.priority)} />
                    </td>
                    <td className="px-4 py-3.5">
                      <Badge dot text={incident.status} variant={statusVariant(incident.status)} />
                    </td>
                    <td className="whitespace-nowrap px-4 py-3.5 text-sm text-text-2">
                      {new Date(incident.created_at).toLocaleString()}
                    </td>
                    <td className="px-4 py-3.5">
                      {incident.external_item_url ? (
                        <a
                          href={incident.external_item_url}
                          target="_blank"
                          rel="noopener noreferrer"
                          onClick={(e) => e.stopPropagation()}
                          className="text-sm font-medium text-accent hover:text-accent-hover hover:underline underline-offset-2"
                        >
                          View →
                        </a>
                      ) : (
                        <span className="text-text-3">—</span>
                      )}
                    </td>
                  </tr>
                ))}
              </DataTable>
            </>
          )}

          <div className="rounded-lg border border-border bg-surface shadow-xs">
            <Pagination page={data.page} pages={data.pages} total={data.total} onPage={setPage} />
          </div>
        </>
      )}
    </div>
  )
}

function LoadingState() {
  return (
    <div className="space-y-3">
      {[...Array(5)].map((_, i) => (
        <SkeletonBlock key={i} className="h-[72px] rounded-xl" />
      ))}
    </div>
  )
}
