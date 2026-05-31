import { useEffect, useMemo, useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { listDiscoveredTargets, listTargets, upsertTargets } from '../api/targets'
import { Button } from '../components/ui/Button'
import { Card } from '../components/ui/Card'
import { EmptyState } from '../components/ui/EmptyState'
import { PageHeader } from '../components/ui/PageHeader'
import { SkeletonBlock } from '../components/ui/SkeletonBlock'
import { useToast } from '../components/ui/ToastProvider'
import type { TargetEnvironment } from '../types/targets'

export function TargetsPage() {
  const toast = useToast()
  const queryClient = useQueryClient()
  const [environment, setEnvironment] = useState<TargetEnvironment>('local')
  const [selectedKeys, setSelectedKeys] = useState<Set<string>>(new Set())
  const [search, setSearch] = useState('')
  const [typeFilter, setTypeFilter] = useState<'all' | 'container' | 'namespace' | 'workload'>('all')

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
      toast.success('Saved target policy successfully.')
    },
    onError: () => {
      toast.error('Failed to save target policy.')
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

  const loading = discoveredQuery.isLoading || persistedQuery.isLoading
  const hasError = discoveredQuery.isError || persistedQuery.isError

  return (
    <div className="space-y-4">
      <PageHeader
        title="Targets"
        subtitle="Discover runtime targets and choose what RemediAI should monitor."
        actions={
          <select
            value={environment}
            onChange={(event) => setEnvironment(event.target.value as TargetEnvironment)}
            className="h-10 rounded-md border border-border bg-surface px-3 text-sm text-text-1"
          >
            <option value="local" className="bg-surface text-text-1">
              Local
            </option>
            <option value="kubernetes" className="bg-surface text-text-1">
              Kubernetes
            </option>
          </select>
        }
      />

      <Card className="p-4">
        <div className="flex flex-wrap items-center gap-2">
          <input
            value={search}
            onChange={(event) => setSearch(event.target.value)}
            placeholder="Search targets"
            className="h-10 min-w-52 rounded-md border border-border bg-surface px-3 text-sm text-text-1"
          />
          {(['all', 'container', 'namespace', 'workload'] as const).map((kind) => (
            <button
              key={kind}
              type="button"
              onClick={() => setTypeFilter(kind)}
              className={`rounded-full px-3 py-1 text-xs transition-colors ${
                typeFilter === kind
                  ? 'bg-accent text-text-1'
                  : 'border border-border bg-surface text-text-2 hover:text-text-1'
              }`}
            >
              {kind}
            </button>
          ))}
          <div className="ml-auto flex flex-wrap items-center gap-2">
            <Button type="button" size="sm" onClick={enableVisible}>
              Enable visible
            </Button>
            <Button type="button" size="sm" onClick={disableVisible}>
              Disable visible
            </Button>
            <Button type="button" size="sm" onClick={resetSelection}>
              Reset
            </Button>
          </div>
        </div>
      </Card>

      {loading && (
        <div className="grid grid-cols-1 gap-4 xl:grid-cols-2">
          <SkeletonBlock className="h-64" />
          <SkeletonBlock className="h-64" />
        </div>
      )}

      {!loading && hasError && (
        <EmptyState title="Failed to load targets" description="Check API connectivity and try again." />
      )}

      {!loading && !hasError && (
        <div className="grid grid-cols-1 gap-4 xl:grid-cols-2">
          <Card className="p-4">
            <div className="mb-3 flex items-center justify-between">
              <h2 className="text-sm font-semibold uppercase tracking-wide text-text-2">Discovered targets</h2>
              <span className="text-xs text-text-2">{filteredTargets.length} visible</span>
            </div>

            {filteredTargets.length === 0 ? (
              <EmptyState title="No targets discovered" description={`No targets discovered for ${environment}.`} />
            ) : (
              <div className="space-y-2">
                {filteredTargets.map((target) => (
                  <label
                    key={target.target_key}
                    className="flex cursor-pointer items-center justify-between rounded-lg border border-border bg-surface-2 px-3 py-2"
                  >
                    <div>
                      <p className="text-sm font-medium text-text-1">{target.display_name}</p>
                      <p className="text-xs text-text-2">
                        {target.target_type} - {target.target_key}
                      </p>
                    </div>
                    <input
                      type="checkbox"
                      checked={selectedKeys.has(target.target_key)}
                      onChange={() => toggleTarget(target.target_key)}
                      className="h-4 w-4 accent-accent"
                    />
                  </label>
                ))}
              </div>
            )}
          </Card>

          <Card className="p-4">
            <div className="mb-3 flex items-center justify-between">
              <h2 className="text-sm font-semibold uppercase tracking-wide text-text-2">Selected targets</h2>
              <span className="text-xs text-text-2">{selectedCount} selected</span>
            </div>

            {selectedCount === 0 ? (
              <EmptyState title="No targets enabled" description="Enable at least one target to start receiving incidents." />
            ) : (
              <div className="space-y-2">
                {[...selectedKeys].map((targetKey) => {
                  const found = discovered.find((target) => target.target_key === targetKey)
                  return (
                    <div key={targetKey} className="rounded-lg border border-border bg-surface-2 px-3 py-2">
                      <p className="text-sm font-medium text-text-1">{found?.display_name ?? targetKey}</p>
                      <p className="text-xs text-text-2">{targetKey}</p>
                    </div>
                  )
                })}
              </div>
            )}
          </Card>
        </div>
      )}

      <div className="sticky bottom-20 z-20 rounded-lg border border-border bg-surface/95 p-3 backdrop-blur xl:static xl:rounded-none xl:border-0 xl:bg-transparent xl:p-0">
        <Button
          type="button"
          variant="primary"
          onClick={() => saveMutation.mutate()}
          disabled={saveMutation.isPending || discovered.length === 0}
          className="w-full xl:w-auto"
        >
          {saveMutation.isPending ? 'Saving...' : 'Save target policy'}
        </Button>
      </div>
    </div>
  )
}
