import { useEffect, useMemo, useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { listDiscoveredTargets, listTargets, upsertTargets } from '../api/targets'
import type { TargetEnvironment } from '../types/targets'

export function TargetsPage() {
  const queryClient = useQueryClient()
  const [environment, setEnvironment] = useState<TargetEnvironment>('local')
  const [selectedKeys, setSelectedKeys] = useState<Set<string>>(new Set())
  const [search, setSearch] = useState('')
  const [typeFilter, setTypeFilter] = useState<'all' | 'container' | 'namespace' | 'workload'>('all')
  const [toast, setToast] = useState<{ kind: 'success' | 'error'; text: string } | null>(null)

  const discoveredQuery = useQuery({
    queryKey: ['targets-discovered', environment],
    queryFn: () => listDiscoveredTargets(environment),
  })

  const persistedQuery = useQuery({
    queryKey: ['targets-persisted', environment],
    queryFn: () => listTargets(environment),
  })

  const discovered = discoveredQuery.data ?? []
  const persisted = persistedQuery.data ?? []

  useEffect(() => {
    const next = new Set<string>(
      persisted.filter((target) => target.enabled).map((target) => target.target_key),
    )
    setSelectedKeys(next)
  }, [environment, persistedQuery.data])

  const saveMutation = useMutation({
    mutationFn: () =>
      upsertTargets({
        environment,
        targets: discovered.map((target) => ({
          target_type: target.target_type,
          target_key: target.target_key,
          display_name: target.display_name,
          enabled: selectedKeys.has(target.target_key),
          metadata: target.metadata,
        })),
      }),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ['targets-persisted', environment] })
      setToast({ kind: 'success', text: 'Saved target policy successfully.' })
    },
    onError: () => {
      setToast({ kind: 'error', text: 'Failed to save target policy.' })
    },
  })

  useEffect(() => {
    if (!toast) {
      return
    }
    const timer = window.setTimeout(() => setToast(null), 2500)
    return () => window.clearTimeout(timer)
  }, [toast])

  function toggleTarget(targetKey: string): void {
    setSelectedKeys((current) => {
      const next = new Set(current)
      if (next.has(targetKey)) {
        next.delete(targetKey)
      } else {
        next.add(targetKey)
      }
      return next
    })
  }

  const selectedCount = useMemo(() => selectedKeys.size, [selectedKeys])
  const filteredTargets = useMemo(() => {
    const query = search.trim().toLowerCase()
    return discovered.filter((target) => {
      if (typeFilter !== 'all' && target.target_type !== typeFilter) {
        return false
      }
      if (!query) {
        return true
      }
      return (
        target.display_name.toLowerCase().includes(query) ||
        target.target_key.toLowerCase().includes(query)
      )
    })
  }, [discovered, search, typeFilter])

  function enableVisible(): void {
    setSelectedKeys((current) => {
      const next = new Set(current)
      for (const target of filteredTargets) {
        next.add(target.target_key)
      }
      return next
    })
  }

  function disableVisible(): void {
    setSelectedKeys((current) => {
      const next = new Set(current)
      for (const target of filteredTargets) {
        next.delete(target.target_key)
      }
      return next
    })
  }

  function resetSelection(): void {
    setSelectedKeys(new Set())
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-semibold text-gray-900">Targets</h1>
          <p className="mt-1 text-sm text-gray-500">
            Discover runtime targets and choose what RemediAI should monitor.
          </p>
        </div>
        <select
          value={environment}
          onChange={(event) => setEnvironment(event.target.value as TargetEnvironment)}
          className="rounded border border-gray-300 px-3 py-2 text-sm"
        >
          <option value="local">Local</option>
          <option value="kubernetes">Kubernetes</option>
        </select>
      </div>

      <div className="rounded-lg border border-gray-200 bg-white p-4 shadow-sm">
        <div className="mb-3 flex items-center justify-between">
          <h2 className="text-sm font-semibold text-gray-900">Discovered targets</h2>
          <span className="text-xs text-gray-500">Selected: {selectedCount}</span>
        </div>

        <div className="mb-3 flex flex-wrap items-center gap-2">
          <input
            value={search}
            onChange={(event) => setSearch(event.target.value)}
            placeholder="Search targets"
            className="min-w-56 rounded border border-gray-300 px-3 py-1.5 text-sm"
          />
          {(['all', 'container', 'namespace', 'workload'] as const).map((kind) => (
            <button
              key={kind}
              onClick={() => setTypeFilter(kind)}
              className={`rounded-full px-3 py-1 text-xs ${
                typeFilter === kind
                  ? 'bg-indigo-600 text-white'
                  : 'border border-gray-300 bg-white text-gray-700'
              }`}
            >
              {kind}
            </button>
          ))}
          <div className="ml-auto flex items-center gap-2">
            <button
              onClick={enableVisible}
              className="rounded border border-gray-300 px-2 py-1 text-xs text-gray-700"
            >
              Enable visible
            </button>
            <button
              onClick={disableVisible}
              className="rounded border border-gray-300 px-2 py-1 text-xs text-gray-700"
            >
              Disable visible
            </button>
            <button
              onClick={resetSelection}
              className="rounded border border-gray-300 px-2 py-1 text-xs text-gray-700"
            >
              Reset
            </button>
          </div>
        </div>

        {(discoveredQuery.isLoading || persistedQuery.isLoading) && (
          <p className="py-8 text-center text-sm text-gray-500">Loading targets…</p>
        )}

        {(discoveredQuery.isError || persistedQuery.isError) && (
          <p className="py-8 text-center text-sm text-red-600">Failed to load targets.</p>
        )}

        {!discoveredQuery.isLoading && !persistedQuery.isLoading && filteredTargets.length === 0 && (
          <p className="py-8 text-center text-sm text-gray-500">
            No targets discovered for {environment}.
          </p>
        )}

        {!discoveredQuery.isLoading && filteredTargets.length > 0 && (
          <div className="space-y-2">
            {filteredTargets.map((target) => (
              <label
                key={target.target_key}
                className="flex items-center justify-between rounded border border-gray-200 px-3 py-2 text-sm"
              >
                <div>
                  <p className="font-medium text-gray-900">{target.display_name}</p>
                  <p className="text-xs text-gray-500">
                    {target.target_type} · {target.target_key}
                  </p>
                </div>
                <input
                  type="checkbox"
                  checked={selectedKeys.has(target.target_key)}
                  onChange={() => toggleTarget(target.target_key)}
                  className="h-4 w-4 accent-indigo-600"
                />
              </label>
            ))}
          </div>
        )}
      </div>

      <div className="flex items-center gap-3">
        <button
          onClick={() => saveMutation.mutate()}
          disabled={saveMutation.isPending || discovered.length === 0}
          className="rounded bg-indigo-600 px-4 py-2 text-sm font-medium text-white hover:bg-indigo-700 disabled:opacity-50"
        >
          {saveMutation.isPending ? 'Saving…' : 'Save target policy'}
        </button>
        {toast && (
          <span
            className={`text-sm ${
              toast.kind === 'success' ? 'text-green-700' : 'text-red-600'
            }`}
          >
            {toast.text}
          </span>
        )}
      </div>
    </div>
  )
}
