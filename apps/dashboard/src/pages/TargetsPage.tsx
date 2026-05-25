import { useEffect, useMemo, useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { listDiscoveredTargets, listTargets, upsertTargets } from '../api/targets'
import type { TargetEnvironment } from '../types/targets'

export function TargetsPage() {
  const queryClient = useQueryClient()
  const [environment, setEnvironment] = useState<TargetEnvironment>('local')
  const [selectedKeys, setSelectedKeys] = useState<Set<string>>(new Set())

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
    },
  })

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

        {(discoveredQuery.isLoading || persistedQuery.isLoading) && (
          <p className="py-8 text-center text-sm text-gray-500">Loading targets…</p>
        )}

        {(discoveredQuery.isError || persistedQuery.isError) && (
          <p className="py-8 text-center text-sm text-red-600">Failed to load targets.</p>
        )}

        {!discoveredQuery.isLoading && !persistedQuery.isLoading && discovered.length === 0 && (
          <p className="py-8 text-center text-sm text-gray-500">
            No targets discovered for {environment}.
          </p>
        )}

        {!discoveredQuery.isLoading && discovered.length > 0 && (
          <div className="space-y-2">
            {discovered.map((target) => (
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
        {saveMutation.isSuccess && (
          <span className="text-sm text-green-700">Saved target policy successfully.</span>
        )}
        {saveMutation.isError && (
          <span className="text-sm text-red-600">Failed to save target policy.</span>
        )}
      </div>
    </div>
  )
}
