import { clsx } from 'clsx'
import { ArrowDown, ArrowUp, Trash2, Loader2 } from 'lucide-react'
import { Button } from '@/components/ui/Button'
import type { PackBackupSummary } from '../inventory/types'

interface PackStorageActionsProps {
  summary: PackBackupSummary
  backupEnabled: boolean
  backupConnected: boolean
  onPull: () => void
  onPush: () => void
  onPushAndFree: () => void
  isPulling?: boolean
  isPushing?: boolean
  className?: string
}

/**
 * Action buttons for pack-level backup operations.
 * Pull: restore from backup to local
 * Push: backup from local to backup storage
 * Push & Free: backup + delete local copies
 */
export function PackStorageActions({
  summary,
  backupEnabled,
  backupConnected,
  onPull,
  onPush,
  onPushAndFree,
  isPulling = false,
  isPushing = false,
  className,
}: PackStorageActionsProps) {
  // Calculate what actions are available
  const hasBackupOnly = summary.backup_only > 0
  const hasLocalOnly = summary.local_only > 0
  const hasLocal = summary.local_only > 0 || summary.both > 0

  // Can pull if there are backup-only blobs
  const canPull = backupEnabled && backupConnected && hasBackupOnly

  // Can push if there are local-only blobs
  const canPush = backupEnabled && backupConnected && hasLocalOnly

  // Can push & free if there are any local blobs that aren't yet backed up
  // OR if all are synced (we can still free local space)
  const canPushAndFree = backupEnabled && backupConnected && hasLocal

  const isLoading = isPulling || isPushing

  if (!backupEnabled) {
    return (
      <div className={clsx('text-sm text-text-muted italic', className)}>
        Enable backup in Settings to use storage actions
      </div>
    )
  }

  if (!backupConnected) {
    return (
      <div className={clsx('text-sm text-amber-400 italic', className)}>
        Backup storage offline
      </div>
    )
  }

  return (
    <div className={clsx('flex items-center gap-2 flex-wrap', className)}>
      {/* Pull button */}
      <Button
        size="sm"
        variant={canPull ? 'primary' : 'ghost'}
        onClick={onPull}
        disabled={!canPull || isLoading}
        className={clsx(
          'gap-1.5',
          canPull && 'bg-blue-600 hover:bg-blue-500'
        )}
        title={canPull ? `Restore ${summary.backup_only} blobs from backup` : 'No blobs to restore'}
      >
        {isPulling ? (
          <Loader2 className="w-4 h-4 animate-spin" />
        ) : (
          <ArrowDown className="w-4 h-4" />
        )}
        Pull
      </Button>

      {/* Push button */}
      <Button
        size="sm"
        variant={canPush ? 'primary' : 'ghost'}
        onClick={onPush}
        disabled={!canPush || isLoading}
        className={clsx(
          'gap-1.5',
          canPush && 'bg-amber-600 hover:bg-amber-500'
        )}
        title={canPush ? `Backup ${summary.local_only} blobs to backup storage` : 'No blobs to backup'}
      >
        {isPushing && !isPulling ? (
          <Loader2 className="w-4 h-4 animate-spin" />
        ) : (
          <ArrowUp className="w-4 h-4" />
        )}
        Push
      </Button>

      {/* Push & Free Space button */}
      <Button
        size="sm"
        variant="ghost"
        onClick={onPushAndFree}
        disabled={!canPushAndFree || isLoading}
        className="gap-1.5 text-red-400 hover:text-red-300 hover:bg-red-500/10"
        title="Backup to external storage and delete local copies"
      >
        <ArrowUp className="w-4 h-4" />
        <Trash2 className="w-3 h-3" />
        Push & Free
      </Button>
    </div>
  )
}
