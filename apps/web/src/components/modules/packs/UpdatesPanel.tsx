/**
 * UpdatesPanel - Slide-out panel showing available pack updates.
 *
 * Displays check results from updatesStore with:
 * - Per-pack update cards with selection checkboxes
 * - Change details (old → new version per dependency)
 * - Impacted packs warning
 * - Select all / Deselect all
 * - Apply Selected button with options
 * - Batch progress tracking
 * - Aggregate download progress after apply
 */

import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { createPortal } from 'react-dom'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import {
  X,
  RefreshCw,
  Download,
  Loader2,
  CheckSquare,
  Square,
  ChevronDown,
  ChevronRight,
  AlertTriangle,
  Layers,
  Package,
  Check,
  XCircle,
  ExternalLink,
} from 'lucide-react'
import { clsx } from 'clsx'
import { Button } from '@/components/ui/Button'
import { ProgressBar } from '@/components/ui/ProgressBar'
import { useUpdatesStore, type UpdatePlanEntry } from '@/stores/updatesStore'
import { toast } from '@/stores/toastStore'
import { formatBytes, formatSpeed, formatEta } from '@/lib/utils/format'

interface UpdatesPanelProps {
  open: boolean
  onClose: () => void
}

interface DownloadInfo {
  download_id: string
  status: string
  progress: number
  downloaded_bytes: number
  total_bytes: number
  speed_bps: number
  eta_seconds: number | null
  group_id: string | null
}

function UpdateItem({
  packName,
  plan,
  selected,
  applying,
  onToggle,
}: {
  packName: string
  plan: UpdatePlanEntry
  selected: boolean
  applying: boolean
  onToggle: () => void
}) {
  const { t } = useTranslation()
  const [expanded, setExpanded] = useState(false)
  const changesCount = plan.changes.length
  const ambiguousCount = plan.ambiguous.length
  const pendingCount = plan.pending_downloads?.length ?? 0
  const isPendingOnly = changesCount === 0 && ambiguousCount === 0 && pendingCount > 0

  return (
    <div
      className={clsx(
        'rounded-xl border transition-colors',
        isPendingOnly
          ? 'bg-amber-500/5 border-amber-500/30'
          : selected
            ? 'bg-synapse/5 border-synapse/30'
            : 'bg-slate-dark/50 border-slate-mid/30',
        applying && 'opacity-60 pointer-events-none'
      )}
    >
      <div className="flex items-center gap-3 p-4">
        {/* Checkbox */}
        <button
          onClick={onToggle}
          className="shrink-0 text-text-muted hover:text-synapse transition-colors"
          disabled={applying}
        >
          {selected ? (
            <CheckSquare className="w-5 h-5 text-synapse" />
          ) : (
            <Square className="w-5 h-5" />
          )}
        </button>

        {/* Pack info */}
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2">
            <Package className="w-4 h-4 text-text-muted shrink-0" />
            <span className="font-medium text-text-primary truncate">{packName}</span>
          </div>
          <p className="text-sm text-text-muted mt-0.5">
            {isPendingOnly ? (
              <span className="text-amber-400">
                {t('updates.panel.pendingDownloads', { count: pendingCount })}
              </span>
            ) : (
              t('updates.panel.changesCount', { count: changesCount + ambiguousCount })
            )}
          </p>
        </div>

        {/* Status / loading */}
        {applying ? (
          <Loader2 className="w-5 h-5 text-synapse animate-spin shrink-0" />
        ) : (
          <button
            onClick={() => setExpanded(!expanded)}
            className="p-1.5 rounded-lg hover:bg-slate-mid/50 text-text-muted transition-colors shrink-0"
          >
            {expanded ? (
              <ChevronDown className="w-4 h-4" />
            ) : (
              <ChevronRight className="w-4 h-4" />
            )}
          </button>
        )}
      </div>

      {/* Expanded details */}
      {expanded && (
        <div className="px-4 pb-4 space-y-2 border-t border-slate-mid/20 pt-3">
          {/* Pending downloads warning */}
          {pendingCount > 0 && (
            <div className="p-2.5 bg-amber-500/10 border border-amber-500/30 rounded-lg">
              <div className="flex items-center gap-2 mb-1.5">
                <AlertTriangle className="w-3.5 h-3.5 text-amber-400" />
                <p className="text-xs font-medium text-amber-400">
                  {t('updates.panel.pendingDownloadsDetail', { count: pendingCount })}
                </p>
              </div>
              {plan.pending_downloads.map((pd, idx) => (
                <div key={idx} className="text-xs text-text-muted mt-1 ml-5.5">
                  <span className="font-mono text-amber-300">{pd.dependency_id}</span>
                  {pd.size_bytes ? (
                    <span className="ml-2 text-text-muted/70">({formatBytes(pd.size_bytes)})</span>
                  ) : null}
                </div>
              ))}
            </div>
          )}

          {plan.changes.map((change, idx) => {
            const newData = change.new as Record<string, unknown>
            const modelId = newData?.provider_model_id
            const versionId = newData?.provider_version_id
            const civitaiUrl = modelId
              ? `https://civitai.com/models/${modelId}${versionId ? `?modelVersionId=${versionId}` : ''}`
              : null

            return (
              <div key={idx} className="p-2.5 bg-slate-900/50 rounded-lg text-sm">
                <div className="flex items-center justify-between">
                  <p className="font-mono text-synapse text-xs">{change.dependency_id}</p>
                  {civitaiUrl && (
                    <a
                      href={civitaiUrl}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="flex items-center gap-1 text-xs text-text-muted hover:text-synapse transition-colors"
                      title={t('updates.panel.whatsNew')}
                    >
                      <ExternalLink className="w-3 h-3" />
                      <span>{t('updates.panel.whatsNew')}</span>
                    </a>
                  )}
                </div>
                <div className="flex items-center gap-2 mt-1 text-text-muted text-xs">
                  <span>{String((change.old as Record<string, unknown>)?.provider_version_id || '?')}</span>
                  <span className="text-text-muted/50">→</span>
                  <span className="text-pulse">{String(versionId || t('updates.panel.new'))}</span>
                </div>
              </div>
            )
          })}

          {ambiguousCount > 0 && (
            <div className="p-2.5 bg-amber-500/10 border border-amber-500/30 rounded-lg flex items-center gap-2">
              <AlertTriangle className="w-4 h-4 text-amber-400 shrink-0" />
              <p className="text-xs text-amber-400">
                {t('updates.panel.ambiguousCount', { count: ambiguousCount })}
              </p>
            </div>
          )}

          {plan.impacted_packs.length > 0 && (
            <div className="p-2.5 bg-blue-500/10 border border-blue-500/30 rounded-lg">
              <div className="flex items-center gap-2 mb-1.5">
                <Layers className="w-3.5 h-3.5 text-blue-400" />
                <p className="text-xs font-medium text-blue-400">
                  {t('updates.panel.impactedPacks', { count: plan.impacted_packs.length })}
                </p>
              </div>
              <div className="flex flex-wrap gap-1">
                {plan.impacted_packs.map((name) => (
                  <span
                    key={name}
                    className="text-xs px-1.5 py-0.5 bg-blue-500/20 text-blue-300 rounded"
                  >
                    {name}
                  </span>
                ))}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  )
}

function GroupDownloadProgress({ groupId, onCancel }: { groupId: string; onCancel: () => void }) {
  const { t } = useTranslation()

  const { data: downloads } = useQuery<DownloadInfo[]>({
    queryKey: ['downloads-active'],
    queryFn: async () => {
      const res = await fetch('/api/packs/downloads/active')
      if (!res.ok) return []
      return res.json()
    },
    select: (data) => data.filter((d: DownloadInfo) => d.group_id === groupId),
    refetchInterval: (query) => {
      const data = query.state.data as DownloadInfo[] | undefined
      const hasActive = data?.some(d => d.status === 'downloading' || d.status === 'pending')
      return hasActive ? 1500 : false
    },
  })

  if (!downloads || downloads.length === 0) return null

  const totalBytes = downloads.reduce((sum, d) => sum + d.total_bytes, 0)
  const downloadedBytes = downloads.reduce((sum, d) => sum + d.downloaded_bytes, 0)
  const completedCount = downloads.filter(d => d.status === 'completed').length
  const totalCount = downloads.length
  const allCompleted = completedCount === totalCount
  const hasActive = downloads.some(d => d.status === 'downloading' || d.status === 'pending')
  const progress = totalBytes > 0 ? (downloadedBytes / totalBytes) * 100 : 0

  // Aggregate speed and ETA
  const totalSpeed = downloads.reduce((sum, d) => d.status === 'downloading' ? sum + d.speed_bps : sum, 0)
  const remainingBytes = totalBytes - downloadedBytes
  const aggregateEta = totalSpeed > 0 ? remainingBytes / totalSpeed : 0

  if (allCompleted) {
    return (
      <div className="p-3 bg-green-500/10 border border-green-500/30 rounded-xl">
        <div className="flex items-center gap-2">
          <Check className="w-5 h-5 text-green-400" />
          <span className="text-sm font-medium text-green-400">
            {t('updates.panel.downloadComplete')}
          </span>
        </div>
        <p className="text-xs text-text-muted mt-1">
          {formatBytes(totalBytes)} {t('downloads.complete').toLowerCase()}
        </p>
      </div>
    )
  }

  return (
    <div className="space-y-3">
      <ProgressBar progress={progress} showLabel={true} />
      <div className="flex items-center justify-between text-xs text-text-muted">
        <span>
          {t('updates.panel.downloadProgress', { completed: completedCount, total: totalCount })}
        </span>
        {hasActive && totalSpeed > 0 && (
          <span>
            {formatSpeed(totalSpeed)} • {t('updates.panel.estimatedTime', { eta: formatEta(aggregateEta) })}
          </span>
        )}
        {hasActive && totalSpeed === 0 && (
          <span>{t('updates.panel.calculatingEta')}</span>
        )}
      </div>
      <Button
        variant="secondary"
        size="sm"
        className="w-full"
        onClick={onCancel}
      >
        <XCircle className="w-4 h-4" />
        {t('updates.panel.cancelBatch')}
      </Button>
    </div>
  )
}

export function UpdatesPanel({ open, onClose }: UpdatesPanelProps) {
  const { t } = useTranslation()
  const queryClient = useQueryClient()
  const {
    isChecking,
    availableUpdates,
    selectedPacks,
    applyingPacks,
    updatesCount,
    activeGroupId,
    checkAll,
    selectAll,
    deselectAll,
    togglePack,
    applySelected,
    retryAllPending,
    cancelBatch,
  } = useUpdatesStore()

  const [isApplying, setIsApplying] = useState(false)
  const selectedCount = selectedPacks.length
  const packNames = Object.keys(availableUpdates)
  const allSelected = selectedCount === packNames.length && packNames.length > 0

  // Detect if any selected packs have pending downloads
  const hasPendingInSelection = selectedPacks.some(name => {
    const plan = availableUpdates[name]
    return plan && (plan.pending_downloads?.length ?? 0) > 0
  })

  const handleApplySelected = async () => {
    if (selectedCount === 0) return
    setIsApplying(true)

    try {
      // Use retryAllPending which handles both pending downloads and new updates
      if (hasPendingInSelection) {
        const result = await retryAllPending()
        if (result.queued > 0) {
          toast.success(t('updates.panel.retrySuccess', { count: result.queued }))
          queryClient.invalidateQueries({ queryKey: ['packs'] })
        }
        if (result.failed > 0) {
          toast.error(t('updates.panel.applyFailed', { count: result.failed }))
        }
      } else {
        const result = await applySelected()
        if (result.applied > 0) {
          toast.success(t('updates.panel.applySuccess', { count: result.applied }))
          queryClient.invalidateQueries({ queryKey: ['packs'] })
        }
        if (result.failed > 0) {
          toast.error(t('updates.panel.applyFailed', { count: result.failed }))
        }
      }
    } finally {
      setIsApplying(false)
    }
  }

  const handleCheckAll = async () => {
    await checkAll()
    const state = useUpdatesStore.getState()
    if (state.updatesCount > 0) {
      toast.info(t('updates.panel.updatesFound', { count: state.updatesCount }))
    } else {
      toast.success(t('updates.panel.allUpToDate'))
    }
  }

  const handleCancelBatch = async () => {
    await cancelBatch()
    queryClient.invalidateQueries({ queryKey: ['downloads-active'] })
  }

  if (!open) return null

  const panel = (
    <div className="fixed inset-0 z-[80] flex justify-end">
      {/* Backdrop */}
      <div
        className="absolute inset-0 bg-black/60 backdrop-blur-sm"
        onClick={onClose}
      />

      {/* Panel */}
      <div className="relative w-full max-w-md bg-slate-900 border-l border-slate-mid/50 flex flex-col shadow-2xl animate-slide-in-right">
        {/* Header */}
        <div className="flex items-center justify-between p-4 border-b border-slate-mid/50">
          <div className="flex items-center gap-3">
            <div className="p-2 bg-synapse/20 rounded-lg">
              <RefreshCw className="w-5 h-5 text-synapse" />
            </div>
            <div>
              <h2 className="font-semibold text-text-primary">{t('updates.panel.title')}</h2>
              <p className="text-xs text-text-muted">
                {updatesCount > 0
                  ? t('updates.panel.availableCount', { count: updatesCount })
                  : t('updates.panel.noUpdates')}
              </p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="p-2 rounded-lg hover:bg-slate-mid transition-colors text-text-muted"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Content */}
        <div className="flex-1 overflow-y-auto p-4 space-y-3">
          {/* Check button when no updates */}
          {updatesCount === 0 && !isChecking && !activeGroupId && (
            <div className="text-center py-8">
              <RefreshCw className="w-12 h-12 text-slate-mid mx-auto mb-3" />
              <p className="text-text-muted mb-4">{t('updates.panel.checkPrompt')}</p>
              <Button variant="primary" onClick={handleCheckAll}>
                <RefreshCw className="w-4 h-4" />
                {t('updates.panel.checkAll')}
              </Button>
            </div>
          )}

          {/* Checking spinner */}
          {isChecking && (
            <div className="text-center py-8">
              <Loader2 className="w-8 h-8 text-synapse animate-spin mx-auto mb-3" />
              <p className="text-text-muted">{t('updates.panel.checking')}</p>
            </div>
          )}

          {/* Select all / Deselect all */}
          {updatesCount > 0 && !isChecking && (
            <div className="flex items-center justify-between">
              <button
                onClick={allSelected ? deselectAll : selectAll}
                className="flex items-center gap-2 text-sm text-text-muted hover:text-text-primary transition-colors"
              >
                {allSelected ? (
                  <CheckSquare className="w-4 h-4 text-synapse" />
                ) : (
                  <Square className="w-4 h-4" />
                )}
                {allSelected ? t('updates.panel.deselectAll') : t('updates.panel.selectAll')}
              </button>

              <Button
                variant="secondary"
                size="sm"
                onClick={handleCheckAll}
                disabled={isChecking}
              >
                <RefreshCw className={clsx('w-3.5 h-3.5', isChecking && 'animate-spin')} />
                {t('updates.panel.recheck')}
              </Button>
            </div>
          )}

          {/* Update items */}
          {packNames.map((packName) => (
            <UpdateItem
              key={packName}
              packName={packName}
              plan={availableUpdates[packName]}
              selected={selectedPacks.includes(packName)}
              applying={applyingPacks.includes(packName)}
              onToggle={() => togglePack(packName)}
            />
          ))}

          {/* All up to date after check */}
          {updatesCount === 0 && !isChecking && !activeGroupId && useUpdatesStore.getState().lastChecked && (
            <div className="text-center py-8">
              <Check className="w-12 h-12 text-green-400 mx-auto mb-3" />
              <p className="text-text-primary font-medium">{t('updates.panel.allUpToDate')}</p>
              <p className="text-sm text-text-muted mt-1">{t('updates.panel.allUpToDateDesc')}</p>
            </div>
          )}
        </div>

        {/* Footer */}
        {(updatesCount > 0 || activeGroupId) && (
          <div className="p-4 border-t border-slate-mid/50 bg-slate-900/95 space-y-3">
            {/* Aggregate download progress when active */}
            {activeGroupId && (
              <GroupDownloadProgress
                groupId={activeGroupId}
                onCancel={handleCancelBatch}
              />
            )}

            {/* Apply / Retry button when there are updates */}
            {updatesCount > 0 && (
              <Button
                variant="primary"
                className="w-full"
                onClick={handleApplySelected}
                disabled={selectedCount === 0 || isApplying}
              >
                {isApplying ? (
                  <Loader2 className="w-4 h-4 animate-spin" />
                ) : (
                  <Download className="w-4 h-4" />
                )}
                {hasPendingInSelection
                  ? t('updates.panel.retrySelected', { count: selectedCount })
                  : t('updates.panel.applySelected', { count: selectedCount })}
              </Button>
            )}
          </div>
        )}
      </div>
    </div>
  )

  return createPortal(panel, document.body)
}
