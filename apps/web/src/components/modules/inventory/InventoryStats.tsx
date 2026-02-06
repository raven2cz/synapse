/**
 * InventoryStats - Dashboard cards showing inventory summary
 */
import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { useTranslation } from 'react-i18next'
import { clsx } from 'clsx'
import { useNavigate } from 'react-router-dom'
import {
  HardDrive,
  Cloud,
  Zap,
  Trash2,
  Upload,
  Shield,
  AlertTriangle,
  CheckCircle,
  AlertCircle,
  Wrench,
  Settings,
  Database,
  FolderOpen,
  Download,
  ArrowUpDown,
  Check,
  GitBranch,
} from 'lucide-react'
import { Button } from '../../ui/Button'
import { toast } from '../../../stores/toastStore'
import type { InventorySummary, BackupStatus, StateSyncStatusResponse, StateSyncResult } from './types'
import { formatBytes } from './utils'

interface InventoryStatsProps {
  summary?: InventorySummary
  backupStatus?: BackupStatus
  onCleanup: () => void
  onVerify: () => void
  onSyncToBackup: () => void
  onDoctor: () => void
}

// State sync API
const stateSyncApi = {
  async getStatus(): Promise<StateSyncStatusResponse> {
    const res = await fetch('/api/store/state/sync-status')
    if (!res.ok) {
      const errorText = await res.text()
      throw new Error(errorText || 'Failed to fetch state sync status')
    }
    return res.json()
  },
  async sync(direction: string, dryRun: boolean): Promise<StateSyncResult> {
    const res = await fetch('/api/store/state/sync', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ direction, dry_run: dryRun }),
    })
    if (!res.ok) {
      const errorText = await res.text()
      throw new Error(errorText || 'Failed to sync state')
    }
    return res.json()
  },
}

export function InventoryStats({
  summary,
  backupStatus,
  onCleanup,
  onVerify,
  onSyncToBackup,
  onDoctor,
}: InventoryStatsProps) {
  const { t } = useTranslation()
  const navigate = useNavigate()
  const queryClient = useQueryClient()

  // Confirmation dialog state
  const [confirmDialog, setConfirmDialog] = useState<{
    open: boolean
    direction: string
    title: string
    message: string
  } | null>(null)

  const diskUsagePercent = summary?.disk_total
    ? ((summary.bytes_total || 0) / summary.disk_total) * 100
    : 0

  const localOnlyCount = summary?.backup?.blobs_local_only || 0
  const backupOnlyCount = summary?.blobs_backup_only || 0
  const syncedCount = summary?.backup?.blobs_both || 0

  // State sync query
  const { data: stateSyncStatus } = useQuery({
    queryKey: ['state-sync-status'],
    queryFn: stateSyncApi.getStatus,
    enabled: backupStatus?.enabled && backupStatus?.connected,
    refetchInterval: 30000,
  })

  // State sync mutation
  const stateSyncMutation = useMutation({
    mutationFn: async (direction: string) => stateSyncApi.sync(direction, false),
    onSuccess: (result) => {
      queryClient.invalidateQueries({ queryKey: ['state-sync-status'] })
      toast.success(t('inventory.stats.syncedFiles', { count: result.synced_files }))
      setConfirmDialog(null)
    },
    onError: (error: Error) => {
      toast.error(t('inventory.stats.syncFailed', { error: error.message }))
      setConfirmDialog(null)
    },
  })

  const stateNeedsSync =
    (stateSyncStatus?.summary?.local_only || 0) +
    (stateSyncStatus?.summary?.backup_only || 0) +
    (stateSyncStatus?.summary?.modified || 0)

  // Check if state has git with local changes (simple heuristic - check if .git exists)
  const hasGitChanges = stateSyncStatus?.summary?.local_only && stateSyncStatus.summary.local_only > 0

  const handleSyncClick = (direction: string, title: string, message: string) => {
    setConfirmDialog({ open: true, direction, title, message })
  }

  const confirmSync = () => {
    if (confirmDialog) {
      stateSyncMutation.mutate(confirmDialog.direction)
    }
  }

  return (
    <>
      <div className="grid grid-cols-12 gap-4">
        {/* ============================================================ */}
        {/* LEFT COLUMN - Local Storage, Status, Actions (8 cols) */}
        {/* ============================================================ */}
        <div className="col-span-12 lg:col-span-8 space-y-4">
          {/* Top row: Local Storage + Blob Status */}
          <div className="grid grid-cols-2 gap-4">
            {/* Local Storage Card */}
            <div className="rounded-xl border border-slate-mid/50 bg-slate-deep/80 p-4">
              <div className="flex items-center gap-3 mb-4">
                <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-slate-mid/50 to-slate-mid/30 flex items-center justify-center">
                  <HardDrive className="w-5 h-5 text-text-secondary" />
                </div>
                <div>
                  <div className="text-sm font-medium text-text-primary">{t('inventory.stats.localStorage')}</div>
                  <div className="text-xs text-text-muted">{t('inventory.stats.modelFiles', { count: summary?.blobs_total || 0 })}</div>
                </div>
              </div>

              <div className="text-3xl font-bold text-text-primary mb-3">
                {formatBytes(summary?.bytes_total || 0)}
              </div>

              {/* Disk usage bar */}
              <div className="space-y-1">
                <div className="h-2 bg-slate-mid/50 rounded-full overflow-hidden">
                  <div
                    className={clsx(
                      'h-full rounded-full transition-all',
                      diskUsagePercent > 90
                        ? 'bg-gradient-to-r from-red-500 to-red-400'
                        : diskUsagePercent > 70
                          ? 'bg-gradient-to-r from-amber-500 to-amber-400'
                          : 'bg-gradient-to-r from-green-500 to-green-400'
                    )}
                    style={{ width: `${Math.min(diskUsagePercent, 100)}%` }}
                  />
                </div>
                <div className="flex justify-between text-xs text-text-muted">
                  <span>{t('inventory.stats.free', { size: formatBytes(summary?.disk_free || 0) })}</span>
                  <span>{t('inventory.stats.used', { percent: diskUsagePercent.toFixed(0) })}</span>
                </div>
              </div>

              {/* Warning for unbackedup models */}
              {localOnlyCount > 0 && backupStatus?.connected && (
                <div className="mt-3 flex items-center gap-2 text-xs text-amber-400 bg-amber-500/10 rounded-lg px-2 py-1.5">
                  <AlertTriangle className="w-3.5 h-3.5" />
                  <span>{t('inventory.stats.notBackedUp', { count: localOnlyCount })}</span>
                </div>
              )}
            </div>

            {/* Blob Status Card */}
            <div className="rounded-xl border border-slate-mid/50 bg-slate-deep/80 p-4">
              <div className="text-sm font-medium text-text-primary mb-4">{t('inventory.stats.blobStatus')}</div>
              <div className="space-y-3">
                <StatusRow
                  icon={<CheckCircle className="w-4 h-4" />}
                  color="text-green-400"
                  label={t('inventory.stats.referenced')}
                  count={summary?.blobs_referenced || 0}
                />
                <StatusRow
                  icon={<AlertTriangle className="w-4 h-4" />}
                  color="text-gray-400"
                  label={t('inventory.stats.orphan')}
                  count={summary?.blobs_orphan || 0}
                />
                <StatusRow
                  icon={<Cloud className="w-4 h-4" />}
                  color="text-blue-400"
                  label={t('inventory.stats.backupOnly')}
                  count={backupOnlyCount}
                />
                {(summary?.blobs_missing || 0) > 0 && (
                  <StatusRow
                    icon={<AlertCircle className="w-4 h-4" />}
                    color="text-red-400"
                    label={t('inventory.stats.missing')}
                    count={summary?.blobs_missing || 0}
                    highlight
                  />
                )}
              </div>
            </div>
          </div>

          {/* Quick Actions Card - Full width */}
          <div className="rounded-xl border border-slate-mid/50 bg-slate-deep/80 p-4">
            <div className="flex items-center gap-2 mb-3">
              <Zap className="w-4 h-4 text-amber-400" />
              <span className="text-sm font-medium text-text-primary">{t('inventory.stats.quickActions')}</span>
            </div>
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-2">
              {/* Cleanup Orphans - local operation */}
              <QuickActionButton
                onClick={onCleanup}
                icon={<Trash2 className="w-4 h-4" />}
                label={t('inventory.stats.cleanup')}
                count={(summary?.blobs_orphan || 0) > 0 ? summary?.blobs_orphan : undefined}
                tooltip={t('inventory.stats.cleanupTooltip')}
                color="amber"
                disabled={(summary?.blobs_orphan || 0) === 0}
              />

              {/* Verify Integrity - local operation */}
              <QuickActionButton
                onClick={onVerify}
                icon={<Shield className="w-4 h-4" />}
                label={t('inventory.stats.verify')}
                tooltip={t('inventory.stats.verifyTooltip')}
                color="purple"
              />

              {/* Run Doctor - local operation */}
              <QuickActionButton
                onClick={onDoctor}
                icon={<Wrench className="w-4 h-4" />}
                label={t('inventory.stats.doctor')}
                tooltip={t('inventory.stats.doctorTooltip')}
                color="blue"
              />

              {/* Backup Local-only - backup operation (last) */}
              <QuickActionButton
                onClick={onSyncToBackup}
                icon={<Upload className="w-4 h-4" />}
                label={t('inventory.stats.backup')}
                count={localOnlyCount > 0 ? localOnlyCount : undefined}
                tooltip={
                  !backupStatus?.connected
                    ? t('inventory.stats.backupNotConnected')
                    : localOnlyCount === 0
                      ? t('inventory.stats.allBackedUp')
                      : t('inventory.stats.backupTooltip')
                }
                color="synapse"
                disabled={!backupStatus?.connected || localOnlyCount === 0}
              />
            </div>
          </div>
        </div>

        {/* ============================================================ */}
        {/* RIGHT COLUMN - Backup Storage (4 cols) */}
        {/* ============================================================ */}
        <div
          className={clsx(
            'col-span-12 lg:col-span-4 rounded-xl border p-4',
            'bg-slate-deep/80',
            !backupStatus?.connected && backupStatus?.enabled
              ? 'border-amber-500/50'
              : 'border-slate-mid/50'
          )}
        >
          {/* Header */}
          <div className="flex items-center justify-between mb-4">
            <div className="flex items-center gap-2">
              <div className={clsx(
                'w-8 h-8 rounded-lg flex items-center justify-center',
                backupStatus?.connected
                  ? 'bg-green-500/20 text-green-400'
                  : backupStatus?.enabled
                    ? 'bg-amber-500/20 text-amber-400'
                    : 'bg-slate-mid/50 text-text-muted'
              )}>
                <Cloud className="w-4 h-4" />
              </div>
              <div className="text-sm font-medium text-text-primary">{t('inventory.stats.backup')}</div>
            </div>

            {/* Status Badge */}
            {backupStatus?.enabled && (
              <div className={clsx(
                'px-2 py-1 rounded-full text-xs font-medium flex items-center gap-1.5',
                backupStatus?.connected
                  ? 'bg-green-500/20 text-green-400'
                  : 'bg-amber-500/20 text-amber-400'
              )}>
                <span className={clsx(
                  'w-1.5 h-1.5 rounded-full',
                  backupStatus?.connected ? 'bg-green-400' : 'bg-amber-400 animate-pulse'
                )} />
                {backupStatus?.connected ? t('inventory.stats.connected') : t('inventory.stats.offline')}
              </div>
            )}
          </div>

          {!backupStatus?.enabled ? (
            /* Not Enabled State */
            <div className="text-center py-6">
              <div className="w-12 h-12 rounded-xl bg-slate-mid/30 flex items-center justify-center mx-auto mb-3">
                <Cloud className="w-6 h-6 text-text-muted" />
              </div>
              <p className="text-sm text-text-muted mb-3">{t('inventory.stats.notEnabled')}</p>
              <Button
                variant="ghost"
                size="sm"
                leftIcon={<Settings className="w-4 h-4" />}
                onClick={() => navigate('/settings#backup-config')}
              >
                {t('inventory.stats.enableBackup')}
              </Button>
            </div>
          ) : !backupStatus?.connected ? (
            /* Disconnected State */
            <div className="text-center py-6">
              <div className="w-12 h-12 rounded-xl bg-amber-500/20 flex items-center justify-center mx-auto mb-3">
                <AlertCircle className="w-6 h-6 text-amber-400" />
              </div>
              <p className="text-sm text-amber-400 mb-1">{t('inventory.stats.disconnected')}</p>
              <p className="text-xs text-text-muted">{t('inventory.stats.connectDrive')}</p>
            </div>
          ) : (
            /* Connected - Show Models & Packs */
            <div className="space-y-4">
              {/* Model Files Section */}
              <div className="rounded-lg border border-slate-mid/30 bg-slate-mid/10 p-3">
                <div className="flex items-center gap-2 mb-2">
                  <Database className="w-4 h-4 text-synapse" />
                  <span className="text-xs font-medium text-text-primary">{t('inventory.stats.modelFilesTitle')}</span>
                </div>

                <div className="text-xl font-bold text-text-primary mb-2">
                  {formatBytes(summary?.backup?.bytes_synced || 0)}
                </div>

                <div className="grid grid-cols-3 gap-1 text-center">
                  <div className="bg-slate-mid/30 rounded px-2 py-1">
                    <div className="text-sm font-bold text-green-400">{syncedCount}</div>
                    <div className="text-[9px] text-text-muted uppercase">{t('inventory.stats.synced')}</div>
                  </div>
                  <div className="bg-slate-mid/30 rounded px-2 py-1">
                    <div className="text-sm font-bold text-amber-400">{localOnlyCount}</div>
                    <div className="text-[9px] text-text-muted uppercase">{t('inventory.stats.pending')}</div>
                  </div>
                  <div className="bg-slate-mid/30 rounded px-2 py-1">
                    <div className="text-sm font-bold text-blue-400">{backupOnlyCount}</div>
                    <div className="text-[9px] text-text-muted uppercase">{t('inventory.stats.backup')}</div>
                  </div>
                </div>

                {localOnlyCount > 0 && (
                  <Button
                    variant="secondary"
                    size="sm"
                    className="w-full mt-2"
                    onClick={onSyncToBackup}
                    leftIcon={<Upload className="w-3 h-3" />}
                  >
                    {t('inventory.stats.backupPending')}
                  </Button>
                )}
              </div>

              {/* Pack Data Section */}
              <div className="rounded-lg border border-slate-mid/30 bg-slate-mid/10 p-3">
                <div className="flex items-center justify-between mb-2">
                  <div className="flex items-center gap-2">
                    <FolderOpen className="w-4 h-4 text-purple-400" />
                    <span className="text-xs font-medium text-text-primary">{t('inventory.stats.packData')}</span>
                  </div>
                  {stateNeedsSync === 0 && stateSyncStatus && (
                    <span className="text-[10px] text-green-400 flex items-center gap-1">
                      <Check className="w-3 h-3" />
                      {t('inventory.stats.synced')}
                    </span>
                  )}
                </div>

                {/* Git warning */}
                {hasGitChanges && (
                  <div className="flex items-center gap-1.5 text-[10px] text-amber-400 bg-amber-500/10 rounded px-2 py-1 mb-2">
                    <GitBranch className="w-3 h-3" />
                    <span>{t('inventory.stats.localChanges')}</span>
                  </div>
                )}

                {stateSyncStatus ? (
                  <>
                    <div className="text-xs text-text-muted mb-2">
                      {t('inventory.stats.files', { count: stateSyncStatus.summary.total_files })}
                      {stateNeedsSync > 0 && (
                        <span className="text-amber-400 ml-1">{t('inventory.stats.pendingCount', { count: stateNeedsSync })}</span>
                      )}
                    </div>

                    <div className="grid grid-cols-3 gap-1 text-center mb-2">
                      <div className="bg-slate-mid/30 rounded px-2 py-1">
                        <div className="text-sm font-bold text-green-400">{stateSyncStatus.summary.synced}</div>
                        <div className="text-[9px] text-text-muted uppercase">{t('inventory.stats.synced')}</div>
                      </div>
                      <div className="bg-slate-mid/30 rounded px-2 py-1">
                        <div className="text-sm font-bold text-cyan-400">{stateSyncStatus.summary.local_only}</div>
                        <div className="text-[9px] text-text-muted uppercase">{t('inventory.stats.local')}</div>
                      </div>
                      <div className="bg-slate-mid/30 rounded px-2 py-1">
                        <div className="text-sm font-bold text-purple-400">{stateSyncStatus.summary.modified}</div>
                        <div className="text-[9px] text-text-muted uppercase">{t('inventory.stats.modified')}</div>
                      </div>
                    </div>

                    {/* Direct sync buttons with confirmation */}
                    {stateNeedsSync > 0 && (
                      <div className="grid grid-cols-3 gap-1">
                        <button
                          onClick={() => handleSyncClick(
                            'to_backup',
                            t('inventory.stats.pushToBackup'),
                            t('inventory.stats.pushMessage', { count: stateSyncStatus.summary.local_only + stateSyncStatus.summary.modified })
                          )}
                          disabled={stateSyncMutation.isPending}
                          className="px-2 py-1.5 text-[10px] font-medium rounded bg-synapse/20 text-synapse hover:bg-synapse/30 border border-synapse/30 flex items-center justify-center gap-1"
                        >
                          <Upload className="w-3 h-3" />
                          {t('inventory.stats.push')}
                        </button>
                        <button
                          onClick={() => handleSyncClick(
                            'from_backup',
                            t('inventory.stats.pullFromBackup'),
                            t('inventory.stats.pullMessage', { count: stateSyncStatus.summary.backup_only + stateSyncStatus.summary.modified })
                          )}
                          disabled={stateSyncMutation.isPending}
                          className="px-2 py-1.5 text-[10px] font-medium rounded bg-blue-500/20 text-blue-400 hover:bg-blue-500/30 border border-blue-500/30 flex items-center justify-center gap-1"
                        >
                          <Download className="w-3 h-3" />
                          {t('inventory.stats.pull')}
                        </button>
                        <button
                          onClick={() => handleSyncClick(
                            'bidirectional',
                            t('inventory.stats.mergeBothWays'),
                            t('inventory.stats.mergeMessage')
                          )}
                          disabled={stateSyncMutation.isPending}
                          className="px-2 py-1.5 text-[10px] font-medium rounded bg-purple-500/20 text-purple-400 hover:bg-purple-500/30 border border-purple-500/30 flex items-center justify-center gap-1"
                        >
                          <ArrowUpDown className="w-3 h-3" />
                          {t('inventory.stats.merge')}
                        </button>
                      </div>
                    )}
                  </>
                ) : (
                  <div className="text-xs text-text-muted">{t('inventory.stats.loading')}</div>
                )}
              </div>

              {/* Path info */}
              <div className="text-[10px] text-text-muted truncate" title={backupStatus.path}>
                {backupStatus.path}
              </div>
            </div>
          )}
        </div>
      </div>

      {/* Confirmation Dialog */}
      {confirmDialog?.open && (
        <div className="fixed inset-0 z-50 flex items-center justify-center">
          <div
            className="absolute inset-0 bg-obsidian/80 backdrop-blur-sm"
            onClick={() => setConfirmDialog(null)}
          />
          <div className="relative bg-slate-deep border border-slate-mid/50 rounded-xl shadow-2xl p-5 max-w-md mx-4">
            <h3 className="text-lg font-semibold text-text-primary mb-2">{confirmDialog.title}</h3>
            <p className="text-sm text-text-secondary mb-4">{confirmDialog.message}</p>
            <div className="flex gap-3 justify-end">
              <Button
                variant="ghost"
                size="sm"
                onClick={() => setConfirmDialog(null)}
              >
                {t('inventory.stats.cancel')}
              </Button>
              <Button
                variant="primary"
                size="sm"
                onClick={confirmSync}
                isLoading={stateSyncMutation.isPending}
              >
                {t('inventory.stats.confirm')}
              </Button>
            </div>
          </div>
        </div>
      )}
    </>
  )
}

// =============================================================================
// Quick Action Button (styled like Push/Pull/Merge)
// =============================================================================

const COLOR_STYLES = {
  amber: 'bg-amber-500/20 text-amber-400 hover:bg-amber-500/30 border-amber-500/30',
  synapse: 'bg-synapse/20 text-synapse hover:bg-synapse/30 border-synapse/30',
  purple: 'bg-purple-500/20 text-purple-400 hover:bg-purple-500/30 border-purple-500/30',
  blue: 'bg-blue-500/20 text-blue-400 hover:bg-blue-500/30 border-blue-500/30',
  red: 'bg-red-500/20 text-red-400 hover:bg-red-500/30 border-red-500/30',
} as const

interface QuickActionButtonProps {
  onClick: () => void
  icon: React.ReactNode
  label: string
  tooltip: string
  color: keyof typeof COLOR_STYLES
  count?: number
  disabled?: boolean
}

function QuickActionButton({
  onClick,
  icon,
  label,
  tooltip,
  color,
  count,
  disabled,
}: QuickActionButtonProps) {
  const [showTooltip, setShowTooltip] = useState(false)

  return (
    <div className="relative">
      <button
        onClick={onClick}
        disabled={disabled}
        onMouseEnter={() => setShowTooltip(true)}
        onMouseLeave={() => setShowTooltip(false)}
        className={clsx(
          'w-full px-3 py-2.5 text-sm font-medium rounded-lg border',
          'flex items-center justify-center gap-2',
          'transition-colors duration-150',
          disabled
            ? 'opacity-60 cursor-not-allowed bg-slate-mid/20 text-text-muted border-slate-mid/60'
            : COLOR_STYLES[color]
        )}
      >
        {icon}
        <span>{label}</span>
        {count !== undefined && count > 0 && (
          <span className="text-xs opacity-75">({count})</span>
        )}
      </button>

      {/* Tooltip - wider with better text */}
      {showTooltip && !disabled && (
        <div
          className={clsx(
            'absolute bottom-full left-1/2 -translate-x-1/2 mb-2',
            'w-64 px-3 py-2',
            'bg-slate-darker border border-slate-mid/50 rounded-lg shadow-xl',
            'text-xs text-text-secondary leading-relaxed text-center',
            'z-50 pointer-events-none',
            'animate-in fade-in slide-in-from-bottom-1 duration-150'
          )}
        >
          {tooltip}
          {/* Arrow */}
          <div className="absolute top-full left-1/2 -translate-x-1/2 border-4 border-transparent border-t-slate-mid/50" />
        </div>
      )}
    </div>
  )
}

function StatusRow({
  icon,
  color,
  label,
  count,
  highlight = false,
}: {
  icon: React.ReactNode
  color: string
  label: string
  count: number
  highlight?: boolean
}) {
  return (
    <div className={clsx(
      'flex items-center justify-between',
      highlight && 'text-red-400'
    )}>
      <div className={clsx('flex items-center gap-2', color)}>
        {icon}
        <span className="text-sm text-text-secondary">{label}</span>
      </div>
      <span className="font-mono text-sm font-medium text-text-primary">{count}</span>
    </div>
  )
}
