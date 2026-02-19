import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { useTranslation } from 'react-i18next'
import { Download, CheckCircle2, XCircle, Clock, Trash2, RefreshCw, HardDrive, Gauge, Timer, ChevronDown, ChevronRight, Package } from 'lucide-react'
import { Card } from '@/components/ui/Card'
import { Button } from '@/components/ui/Button'
import { ProgressBar } from '@/components/ui/ProgressBar'
import { formatBytes, formatSpeed, formatEta } from '@/lib/utils/format'
import { clsx } from 'clsx'

interface DownloadInfo {
  download_id: string
  pack_name: string
  asset_name: string
  filename: string
  status: string
  progress: number
  downloaded_bytes: number
  total_bytes: number
  speed_bps: number
  eta_seconds: number | null
  error: string | null
  started_at: string
  completed_at: string | null
  target_path: string | null
  group_id: string | null
  group_label: string | null
}

function DownloadCard({
  download,
  getStatusIcon,
  getStatusColor,
  onDismiss,
  t,
}: {
  download: DownloadInfo
  getStatusIcon: (status: string) => React.ReactNode
  getStatusColor: (status: string) => string
  onDismiss: (id: string) => void
  t: (key: string, opts?: Record<string, unknown>) => string
}) {
  return (
    <Card
      className={clsx(
        "space-y-4",
        download.status === 'downloading' && "border-synapse/50",
        download.status === 'completed' && "border-green-500/50",
        download.status === 'failed' && "border-red-500/50"
      )}
    >
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          {getStatusIcon(download.status)}
          <div>
            <h3 className="font-semibold text-text-primary">
              {download.asset_name}
            </h3>
            <p className="text-xs text-text-muted">
              {download.pack_name} • {download.filename}
            </p>
          </div>
        </div>
        <div className="flex items-center gap-3">
          <span className={clsx(
            'text-sm font-medium',
            getStatusColor(download.status)
          )}>
            {t(`downloads.status.${download.status}`)}
          </span>
          {['completed', 'failed', 'cancelled'].includes(download.status) && (
            <Button
              variant="ghost"
              size="sm"
              onClick={() => onDismiss(download.download_id)}
              className="text-text-muted hover:text-text-primary"
              title={t('downloads.dismiss')}
            >
              <XCircle className="w-4 h-4" />
            </Button>
          )}
        </div>
      </div>

      {/* Progress for downloading */}
      {download.status === 'downloading' && (
        <div className="space-y-3">
          <ProgressBar
            progress={download.progress}
            showLabel={true}
          />
          <div className="flex items-center justify-between text-xs text-text-muted">
            <div className="flex items-center gap-4">
              <span className="flex items-center gap-1">
                <HardDrive className="w-3 h-3" />
                {formatBytes(download.downloaded_bytes)} / {formatBytes(download.total_bytes)}
              </span>
              <span className="flex items-center gap-1">
                <Gauge className="w-3 h-3" />
                {formatSpeed(download.speed_bps)}
              </span>
            </div>
            <span className="flex items-center gap-1">
              <Timer className="w-3 h-3" />
              {t('downloads.eta', { eta: download.eta_seconds != null && download.eta_seconds > 0 ? formatEta(download.eta_seconds) : '--' })}
            </span>
          </div>
        </div>
      )}

      {/* Pending state */}
      {download.status === 'pending' && (
        <div className="flex items-center gap-2 text-sm text-amber-400">
          <Clock className="w-4 h-4 animate-pulse" />
          <span>{t('downloads.waiting')}</span>
        </div>
      )}

      {/* Completed info */}
      {download.status === 'completed' && (
        <div className="space-y-2">
          <div className="flex justify-between text-sm">
            <span className="text-green-400 flex items-center gap-2">
              <CheckCircle2 className="w-4 h-4" />
              {t('downloads.complete')}
            </span>
            <span className="text-text-muted">
              {formatBytes(download.total_bytes)}
            </span>
          </div>
          {download.target_path && (
            <div className="text-xs text-text-muted truncate" title={download.target_path}>
              {t('downloads.savedTo', { path: download.target_path })}
            </div>
          )}
        </div>
      )}

      {/* Error */}
      {download.error && (
        <div className="p-3 bg-red-500/10 rounded-lg border border-red-500/20">
          <p className="text-sm text-red-400">{download.error}</p>
        </div>
      )}

      {/* Timestamps */}
      <div className="text-xs text-text-muted pt-2 border-t border-white/5">
        {t('downloads.started', { time: new Date(download.started_at).toLocaleString() })}
        {download.completed_at && (
          <> • {t('downloads.completed', { time: new Date(download.completed_at).toLocaleString() })}</>
        )}
      </div>
    </Card>
  )
}

function DownloadGroup({
  groupId,
  groupLabel,
  items,
  getStatusIcon,
  getStatusColor,
  onDismiss,
  onCancelGroup,
  t,
}: {
  groupId: string
  groupLabel: string
  items: DownloadInfo[]
  getStatusIcon: (status: string) => React.ReactNode
  getStatusColor: (status: string) => string
  onDismiss: (id: string) => void
  onCancelGroup: (groupId: string) => void
  t: (key: string, opts?: Record<string, unknown>) => string
}) {
  const [expanded, setExpanded] = useState(true)

  const completedCount = items.filter(d => d.status === 'completed').length
  const totalCount = items.length
  const hasActive = items.some(d => d.status === 'downloading' || d.status === 'pending')

  // Aggregate progress
  const totalBytes = items.reduce((sum, d) => sum + d.total_bytes, 0)
  const downloadedBytes = items.reduce((sum, d) => sum + d.downloaded_bytes, 0)
  const aggregateProgress = totalBytes > 0 ? (downloadedBytes / totalBytes) * 100 : 0

  return (
    <div className="space-y-2">
      {/* Group header */}
      <div className={clsx(
        "flex items-center gap-3 p-3 rounded-xl border",
        hasActive ? "bg-synapse/5 border-synapse/30" : "bg-slate-dark/50 border-slate-mid/30"
      )}>
        <button
          onClick={() => setExpanded(!expanded)}
          className="p-1 rounded-lg hover:bg-slate-mid/50 text-text-muted transition-colors shrink-0"
          title={expanded ? t('downloads.group.collapseGroup') : t('downloads.group.expandGroup')}
        >
          {expanded ? (
            <ChevronDown className="w-4 h-4" />
          ) : (
            <ChevronRight className="w-4 h-4" />
          )}
        </button>

        <Package className="w-4 h-4 text-synapse shrink-0" />

        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2">
            <span className="font-medium text-text-primary text-sm">
              {groupLabel || t('downloads.group.packUpdates')}
            </span>
            <span className="text-xs text-text-muted">
              {t('downloads.group.progress', { completed: completedCount, total: totalCount })}
            </span>
          </div>
          {hasActive && (
            <div className="mt-1.5">
              <ProgressBar progress={aggregateProgress} showLabel={false} size="sm" />
            </div>
          )}
        </div>

        {hasActive && (
          <Button
            variant="ghost"
            size="sm"
            onClick={() => onCancelGroup(groupId)}
            className="text-red-400 hover:text-red-300 shrink-0"
          >
            {t('downloads.group.cancelAll')}
          </Button>
        )}
      </div>

      {/* Group items */}
      {expanded && (
        <div className="space-y-3 pl-4 border-l-2 border-slate-mid/20 ml-4">
          {items.map(download => (
            <DownloadCard
              key={download.download_id}
              download={download}
              getStatusIcon={getStatusIcon}
              getStatusColor={getStatusColor}
              onDismiss={onDismiss}
              t={t}
            />
          ))}
        </div>
      )}
    </div>
  )
}

export function DownloadsPage() {
  const { t } = useTranslation()
  const { data: downloads, isLoading, refetch } = useQuery<DownloadInfo[]>({
    queryKey: ['downloads-active'],
    queryFn: async () => {
      const res = await fetch('/api/packs/downloads/active')
      if (!res.ok) {
        console.error('[DownloadsPage] Failed to fetch downloads')
        return []
      }
      return res.json()
    },
    // Poll only when there are active (non-completed) downloads
    refetchInterval: (query) => {
      const data = query.state.data as DownloadInfo[] | undefined
      const hasActive = data?.some((d: DownloadInfo) => d.status === 'downloading' || d.status === 'pending')
      return hasActive ? 2000 : false
    },
  })

  const clearCompleted = async () => {
    await fetch('/api/packs/downloads/completed', { method: 'DELETE' })
    refetch()
  }

  const dismissDownload = async (downloadId: string) => {
    await fetch(`/api/packs/downloads/${downloadId}`, { method: 'DELETE' })
    refetch()
  }

  const cancelGroup = async (groupId: string) => {
    await fetch(`/api/packs/downloads/group/${encodeURIComponent(groupId)}`, { method: 'DELETE' })
    refetch()
  }

  const getStatusIcon = (status: string) => {
    switch (status) {
      case 'completed':
        return <CheckCircle2 className="w-5 h-5 text-green-400" />
      case 'failed':
      case 'cancelled':
        return <XCircle className="w-5 h-5 text-red-400" />
      case 'downloading':
        return <Download className="w-5 h-5 text-synapse animate-pulse" />
      default:
        return <Clock className="w-5 h-5 text-amber-400" />
    }
  }

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'completed':
        return 'text-green-400'
      case 'failed':
      case 'cancelled':
        return 'text-red-400'
      case 'downloading':
        return 'text-synapse'
      default:
        return 'text-amber-400'
    }
  }

  // Partition into grouped and ungrouped
  const grouped = new Map<string, { label: string; items: DownloadInfo[] }>()
  const ungrouped: DownloadInfo[] = []

  if (downloads) {
    for (const d of downloads) {
      if (d.group_id) {
        const existing = grouped.get(d.group_id)
        if (existing) {
          existing.items.push(d)
        } else {
          grouped.set(d.group_id, { label: d.group_label || '', items: [d] })
        }
      } else {
        ungrouped.push(d)
      }
    }
  }

  // Count active downloads
  const activeCount = downloads?.filter(d => ['pending', 'downloading'].includes(d.status)).length || 0

  return (
    <div className="max-w-4xl mx-auto">
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold text-text-primary flex items-center gap-3">
            {t('downloads.title')}
            {activeCount > 0 && (
              <span className="px-2 py-0.5 bg-synapse/20 text-synapse text-sm rounded-full">
                {t('downloads.active', { count: activeCount })}
              </span>
            )}
          </h1>
          <p className="text-text-secondary mt-1">
            {t('downloads.subtitle')}
          </p>
        </div>
        <div className="flex items-center gap-3">
          <Button
            variant="ghost"
            size="sm"
            onClick={() => refetch()}
          >
            <RefreshCw className="w-4 h-4" />
            {t('downloads.refresh')}
          </Button>
          {downloads && downloads.some(d => ['completed', 'failed', 'cancelled'].includes(d.status)) && (
            <Button
              variant="secondary"
              size="sm"
              onClick={clearCompleted}
            >
              <Trash2 className="w-4 h-4" />
              {t('downloads.clearAll')}
            </Button>
          )}
        </div>
      </div>

      {/* Loading */}
      {isLoading && (
        <div className="space-y-4">
          {[1, 2, 3].map((i) => (
            <Card key={i} className="h-24 skeleton" />
          ))}
        </div>
      )}

      {/* Empty state */}
      {!isLoading && (!downloads || downloads.length === 0) && (
        <Card className="p-12 text-center">
          <Download className="w-12 h-12 text-text-muted mx-auto mb-4" />
          <h3 className="text-lg font-medium text-text-primary mb-2">
            {t('downloads.empty')}
          </h3>
          <p className="text-text-secondary">
            {t('downloads.emptyHint')}
          </p>
        </Card>
      )}

      {/* Downloads list */}
      {downloads && downloads.length > 0 && (
        <div className="space-y-4">
          {/* Grouped downloads */}
          {Array.from(grouped.entries()).map(([groupId, { label, items }]) => (
            <DownloadGroup
              key={groupId}
              groupId={groupId}
              groupLabel={label}
              items={items}
              getStatusIcon={getStatusIcon}
              getStatusColor={getStatusColor}
              onDismiss={dismissDownload}
              onCancelGroup={cancelGroup}
              t={t}
            />
          ))}

          {/* Ungrouped downloads */}
          {ungrouped.map((download) => (
            <DownloadCard
              key={download.download_id}
              download={download}
              getStatusIcon={getStatusIcon}
              getStatusColor={getStatusColor}
              onDismiss={dismissDownload}
              t={t}
            />
          ))}
        </div>
      )}
    </div>
  )
}
