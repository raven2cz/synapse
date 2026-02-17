import { useState, useEffect, useRef } from 'react'
import { useTranslation } from 'react-i18next'
import {
  X,
  ArrowUp,
  Trash2,
  Loader2,
  AlertTriangle,
  CheckCircle,
  XCircle,
  RotateCcw,
} from 'lucide-react'
import { Button } from '@/components/ui/Button'
import { formatBytes } from '@/lib/utils/format'
import { clsx } from 'clsx'
import { useTransferOperation, type TransferOperationItem } from '../inventory/useTransferOperation'
import type { PackBlobStatus } from '../inventory/types'

interface PushConfirmDialogProps {
  isOpen: boolean
  onClose: () => void
  onConfirm: (cleanup: boolean) => void
  onComplete?: () => void
  packName: string
  blobs: PackBlobStatus[]
  isLoading?: boolean
  initialCleanup?: boolean
  backupFn?: (sha256: string) => Promise<void>
  deleteFn?: (sha256: string) => Promise<void>
}

function formatDuration(seconds: number): string {
  if (seconds < 60) return `${Math.round(seconds)}s`
  if (seconds < 3600) {
    const mins = Math.floor(seconds / 60)
    const secs = Math.round(seconds % 60)
    return `${mins}m ${secs}s`
  }
  const hours = Math.floor(seconds / 3600)
  const mins = Math.floor((seconds % 3600) / 60)
  return `${hours}h ${mins}m`
}

function formatSpeed(bytesPerSecond: number): string {
  if (bytesPerSecond < 1024) return `${bytesPerSecond.toFixed(0)} B/s`
  if (bytesPerSecond < 1024 * 1024) return `${(bytesPerSecond / 1024).toFixed(1)} KB/s`
  return `${(bytesPerSecond / (1024 * 1024)).toFixed(1)} MB/s`
}

/**
 * Confirmation dialog for pushing (backing up) pack blobs to backup storage.
 * Includes optional cleanup checkbox to delete local copies after backup.
 * Shows real-time progress after user confirms.
 */
export function PushConfirmDialog({
  isOpen,
  onClose,
  onConfirm,
  onComplete,
  packName,
  blobs,
  isLoading = false,
  initialCleanup = false,
  backupFn,
  deleteFn,
}: PushConfirmDialogProps) {
  const { t } = useTranslation()
  const [cleanup, setCleanup] = useState(initialCleanup)
  const [cleanupPhase, setCleanupPhase] = useState(false)
  // R2: Use ref to prevent double-triggering cleanup phase due to stale closure
  const cleanupStartedRef = useRef(false)

  // R1: Sync cleanup state when initialCleanup prop changes
  useEffect(() => {
    setCleanup(initialCleanup)
  }, [initialCleanup])

  // Use the unified transfer operation hook
  const {
    progress,
    isRunning,
    isCompleted,
    isFailed,
    hasFailed,
    start,
    cancel,
    retryFailed,
    reset,
  } = useTransferOperation({
    operation: cleanupPhase ? 'cleanup' : 'backup',
    onComplete: async () => {
      // If cleanup is enabled and we just finished backup phase, start cleanup phase
      // R2: Use ref to prevent double-triggering due to stale closure capturing old cleanupPhase value
      if (cleanup && !cleanupStartedRef.current && deleteFn) {
        cleanupStartedRef.current = true
        setCleanupPhase(true)
        // Get blobs that actually have local copies to delete
        // Filter out backup_only blobs (location === 'backup_only' means on_local should be false)
        // This prevents infinite loops when cache shows on_local=true but blob is actually backup_only
        const blobsToDelete = blobs.filter(b => b.on_local && b.location !== 'backup_only')
        if (blobsToDelete.length === 0) {
          // Nothing to delete, operation complete
          onComplete?.()
          return
        }
        const deleteItems: TransferOperationItem[] = blobsToDelete.map(blob => ({
          sha256: blob.sha256,
          display_name: blob.display_name,
          size_bytes: blob.size_bytes,
        }))
        await start(deleteItems, deleteFn)
      } else {
        onComplete?.()
      }
    },
  })

  // Reset state when dialog closes
  useEffect(() => {
    if (!isOpen) {
      reset()
      setCleanupPhase(false)
      cleanupStartedRef.current = false
    }
  }, [isOpen, reset])

  if (!isOpen) return null

  // Blobs that need backup (local only)
  const blobsToBackup = blobs.filter(b => b.location === 'local_only')
  // All local blobs (for cleanup calculation) - MUST filter out backup_only to prevent infinite loops
  // backup_only blobs have location='backup_only' even if on_local might be true in stale cache
  const localBlobs = blobs.filter(b => b.on_local && b.location !== 'backup_only')
  const totalBytesToBackup = blobsToBackup.reduce((sum, b) => sum + b.size_bytes, 0)
  const totalBytesToFree = localBlobs.reduce((sum, b) => sum + b.size_bytes, 0)

  // Calculate active bytes based on phase
  const activeItems = cleanupPhase ? localBlobs : blobsToBackup
  const totalBytes = cleanupPhase ? totalBytesToFree : totalBytesToBackup

  // P2: Can confirm if there's something to backup OR cleanup is enabled and there are local blobs
  const canConfirm = blobsToBackup.length > 0 || (cleanup && localBlobs.length > 0)

  // Calculate progress values
  const transferredBytes = progress?.transferred_bytes || 0
  const completedItems = progress?.completed_items || 0
  const failedItems = progress?.failed_items || 0
  const totalItems = progress?.total_items || activeItems.length
  // Force 100% when completed (progress might not update in time for fast operations)
  const progressPercent = isCompleted ? 100 : (totalBytes > 0 ? (transferredBytes / totalBytes) * 100 : 0)
  const bytesPerSecond = progress?.bytes_per_second || 0
  const etaSeconds = progress?.eta_seconds
  const elapsedSeconds = progress?.elapsed_seconds || 0

  // Show progress view if operation has started
  const showProgress = progress !== null || isRunning

  // Determine what the dialog should show - free only mode when all already backed up
  const isFreeOnly = blobsToBackup.length === 0 && cleanup && localBlobs.length > 0

  const handleConfirm = async () => {
    if (!backupFn) {
      // Fallback to legacy behavior if backupFn not provided
      onConfirm(cleanup)
      return
    }

    // If there are blobs to backup, start backup phase
    if (blobsToBackup.length > 0) {
      const items: TransferOperationItem[] = blobsToBackup.map(blob => ({
        sha256: blob.sha256,
        display_name: blob.display_name,
        size_bytes: blob.size_bytes,
      }))
      await start(items, backupFn)
    } else if (cleanup && deleteFn && localBlobs.length > 0) {
      // If only cleanup (no backup needed), go straight to cleanup phase
      setCleanupPhase(true)
      const deleteItems: TransferOperationItem[] = localBlobs.map(blob => ({
        sha256: blob.sha256,
        display_name: blob.display_name,
        size_bytes: blob.size_bytes,
      }))
      await start(deleteItems, deleteFn)
    }
  }

  const handleClose = () => {
    if (isRunning) {
      cancel()
    }
    onClose()
  }

  // Get current phase label
  const phaseLabel = cleanupPhase ? t('pushDialog.freeingSpace') : t('pushDialog.backingUp')
  const completedLabel = cleanupPhase ? t('pushDialog.freed', { count: completedItems }) : t('pushDialog.backedUp', { count: completedItems })

  return (
    <div
      className="fixed inset-0 bg-black/80 backdrop-blur-sm flex items-center justify-center z-50 p-4"
      onClick={isCompleted || isFailed ? handleClose : undefined}
    >
      <div
        className="bg-slate-deep border border-slate-mid rounded-2xl max-w-lg w-full overflow-hidden"
        onClick={e => e.stopPropagation()}
      >
        {/* Header */}
        <div className="bg-gradient-to-r from-amber-500/20 to-orange-500/20 border-b border-amber-500/30 p-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <div className="p-2 bg-amber-500/20 rounded-xl">
                {cleanupPhase ? (
                  <Trash2 className="w-6 h-6 text-amber-400" />
                ) : (
                  <ArrowUp className="w-6 h-6 text-amber-400" />
                )}
              </div>
              <div>
                <h2 className="text-lg font-bold text-text-primary">
                  {showProgress
                    ? cleanupPhase
                      ? t('pushDialog.titleFreeingRunning')
                      : t('pushDialog.titleBackingUpRunning')
                    : isFreeOnly
                      ? t('pushDialog.titleFree')
                      : t('pushDialog.titlePush')}
                </h2>
                <p className="text-sm text-text-muted">{packName}</p>
              </div>
            </div>
            {(isCompleted || isFailed || !showProgress) && (
              <button
                onClick={handleClose}
                disabled={isLoading && !showProgress}
                className="p-2 hover:bg-slate-mid rounded-xl text-text-muted hover:text-text-primary transition-colors disabled:opacity-50"
              >
                <X className="w-5 h-5" />
              </button>
            )}
          </div>
        </div>

        {/* Content */}
        <div className="p-4 space-y-4">
          {!showProgress ? (
            // Confirmation view
            <>
              {/* Show backup info only if there are blobs to backup */}
              {blobsToBackup.length > 0 ? (
                <>
                  <p className="text-text-secondary">
                    {t('pushDialog.backupBlobs', { count: blobsToBackup.length })}
                  </p>

                  {/* Blob list */}
                  <div className="max-h-48 overflow-y-auto space-y-2 bg-slate-dark/50 rounded-xl p-3">
                    {blobsToBackup.map(blob => (
                      <div
                        key={blob.sha256}
                        className="flex items-center justify-between text-sm py-1"
                      >
                        <span className="text-text-primary truncate flex-1 mr-2">
                          {blob.display_name}
                        </span>
                        <span className="text-text-muted flex-shrink-0">
                          {formatBytes(blob.size_bytes)}
                        </span>
                      </div>
                    ))}
                  </div>

                  {/* Total */}
                  <div className="flex items-center justify-between pt-2 border-t border-slate-mid">
                    <span className="text-text-muted">{t('pushDialog.totalToBackup')}</span>
                    <span className="font-bold text-text-primary">{formatBytes(totalBytesToBackup)}</span>
                  </div>
                </>
              ) : (
                <p className="text-text-muted text-sm italic">
                  {t('pushDialog.allBackedUp')}
                </p>
              )}

              {/* Cleanup checkbox */}
              <label className="flex items-start gap-3 p-3 bg-red-500/10 border border-red-500/30 rounded-xl cursor-pointer hover:bg-red-500/15 transition-colors">
                <input
                  type="checkbox"
                  checked={cleanup}
                  onChange={e => setCleanup(e.target.checked)}
                  disabled={localBlobs.length === 0}
                  className="mt-1 w-4 h-4 rounded border-red-500 text-red-500 focus:ring-red-500 bg-slate-dark disabled:opacity-50"
                />
                <div className="flex-1">
                  <div className="flex items-center gap-2 text-red-400 font-medium">
                    <Trash2 className="w-4 h-4" />
                    {t('pushDialog.deleteLocal')}
                  </div>
                  {cleanup && localBlobs.length > 0 && (
                    <p className="text-sm text-red-300 mt-1">
                      {t('pushDialog.freeSize', { size: formatBytes(totalBytesToFree) })}
                    </p>
                  )}
                  {localBlobs.length === 0 && (
                    <p className="text-sm text-text-muted mt-1">{t('pushDialog.noLocalCopies')}</p>
                  )}
                </div>
              </label>

              {/* Warning for cleanup */}
              {cleanup && localBlobs.length > 0 && (
                <div className="flex items-start gap-2 p-3 bg-amber-500/10 rounded-xl text-sm">
                  <AlertTriangle className="w-4 h-4 text-amber-400 flex-shrink-0 mt-0.5" />
                  <span className="text-amber-300">
                    {t('pushDialog.pullWarning')} <code className="bg-slate-dark px-1 rounded">{t('pushDialog.pullLabel')}</code> {t('pushDialog.pullWarningEnd')}
                  </span>
                </div>
              )}
            </>
          ) : (
            // Progress view
            <>
              {/* Phase indicator */}
              {cleanup && !cleanupPhase && blobsToBackup.length > 0 && (
                <div className="text-xs text-text-muted mb-2">
                  {t('pushDialog.step1')}
                </div>
              )}
              {cleanupPhase && (
                <div className="text-xs text-text-muted mb-2">
                  {t('pushDialog.step2')}
                </div>
              )}

              {/* Progress Bar */}
              <div className="space-y-2">
                <div className="flex justify-between text-sm">
                  <span className="text-text-secondary">
                    {isCompleted
                      ? completedLabel
                      : isFailed
                        ? t('pushDialog.completedAndFailed', { count: completedItems, count2: failedItems })
                        : `${phaseLabel}...`}
                  </span>
                  <span className="text-text-primary font-medium">{progressPercent.toFixed(0)}%</span>
                </div>

                <div className="h-3 bg-slate-mid/50 rounded-full overflow-hidden">
                  <div
                    className={clsx(
                      'h-full rounded-full transition-all duration-300',
                      isCompleted && 'bg-gradient-to-r from-green-500 to-green-400',
                      isFailed && 'bg-gradient-to-r from-red-500 to-red-400',
                      !isCompleted && !isFailed && cleanupPhase && 'bg-gradient-to-r from-red-500 to-orange-400',
                      !isCompleted && !isFailed && !cleanupPhase && 'bg-gradient-to-r from-amber-500 to-orange-400'
                    )}
                    style={{ width: `${progressPercent}%` }}
                  />
                </div>

                <div className="flex justify-between text-xs text-text-muted">
                  <span>
                    {formatBytes(isCompleted ? totalBytes : transferredBytes)} / {formatBytes(totalBytes)}
                  </span>
                  {isRunning && bytesPerSecond > 0 && (
                    <span>
                      {formatSpeed(bytesPerSecond)}
                      {etaSeconds !== undefined && etaSeconds > 0 && ` · ${t('pushDialog.remaining', { duration: formatDuration(etaSeconds) })}`}
                    </span>
                  )}
                  {isCompleted && elapsedSeconds > 0 && <span>{t('pushDialog.completedIn', { duration: formatDuration(elapsedSeconds) })}</span>}
                </div>
              </div>

              {/* Current File (when running) */}
              {isRunning && progress?.current_item && (
                <div className="bg-slate-mid/20 rounded-lg px-4 py-3">
                  <div className="flex items-center gap-2">
                    <Loader2 className={clsx(
                      'w-4 h-4 animate-spin flex-shrink-0',
                      cleanupPhase ? 'text-red-400' : 'text-amber-400'
                    )} />
                    <span className="text-sm text-text-secondary truncate flex-1">
                      {progress.current_item.display_name}
                    </span>
                    <span className="text-xs text-text-muted flex-shrink-0">
                      {formatBytes(progress.current_item.size_bytes)}
                    </span>
                  </div>
                </div>
              )}

              {/* Item counter during processing */}
              {isRunning && (
                <div className="text-sm text-text-muted text-center">
                  {t('pushDialog.processing', { current: completedItems + failedItems + 1, total: totalItems })}
                </div>
              )}

              {/* Status Messages */}
              {isCompleted && !hasFailed && !cleanup && (
                <div className="flex items-center gap-3 bg-green-500/10 border border-green-500/30 rounded-lg px-4 py-3">
                  <CheckCircle className="w-5 h-5 text-green-400 flex-shrink-0" />
                  <span className="text-sm text-green-400">
                    {t('pushDialog.successBackup', { count: completedItems })}
                  </span>
                </div>
              )}

              {isCompleted && !hasFailed && cleanupPhase && (
                <div className="flex items-center gap-3 bg-green-500/10 border border-green-500/30 rounded-lg px-4 py-3">
                  <CheckCircle className="w-5 h-5 text-green-400 flex-shrink-0" />
                  <span className="text-sm text-green-400">
                    {/* Use progress.total_bytes which reflects actual items processed */}
                    {(progress?.total_bytes || 0) > 0
                      ? t('pushDialog.successFree', { size: formatBytes(progress?.total_bytes || 0) })
                      : t('pushDialog.alreadyFreed')}
                  </span>
                </div>
              )}

              {hasFailed && (
                <div className="bg-red-500/10 border border-red-500/30 rounded-lg px-4 py-3">
                  <div className="flex items-center gap-3">
                    <XCircle className="w-5 h-5 text-red-400 flex-shrink-0" />
                    <div className="flex-1">
                      <span className="text-sm text-red-400">
                        {t('pushDialog.filesFailed', { count: failedItems })}
                      </span>
                    </div>
                  </div>

                  {progress?.errors && progress.errors.length > 0 && (
                    <div className="mt-3 pt-3 border-t border-red-500/20 space-y-1 max-h-32 overflow-y-auto">
                      {progress.errors.slice(0, 5).map((error, i) => (
                        <div key={i} className="text-xs text-red-400/80 truncate">
                          {error}
                        </div>
                      ))}
                      {progress.errors.length > 5 && (
                        <div className="text-xs text-red-400/60">{t('pushDialog.moreErrors', { count: progress.errors.length - 5 })}</div>
                      )}
                    </div>
                  )}
                </div>
              )}
            </>
          )}
        </div>

        {/* Actions */}
        <div className="flex items-center justify-between px-4 py-4 border-t border-slate-mid bg-slate-mid/10">
          <div className="text-xs text-text-muted">
            {showProgress
              ? t('pushDialog.filesProgress', { completed: completedItems, total: totalItems })
              : blobsToBackup.length > 0
                ? t('pushDialog.filesInfo', { count: blobsToBackup.length, size: formatBytes(totalBytesToBackup) })
                : cleanup && localBlobs.length > 0
                  ? t('pushDialog.filesToFree', { count: localBlobs.length })
                  : t('pushDialog.noFiles')}
          </div>

          <div className="flex gap-2">
            {!showProgress && (
              <>
                <Button
                  variant="ghost"
                  onClick={handleClose}
                  disabled={isLoading}
                >
                  {t('common.cancel')}
                </Button>
                <Button
                  onClick={handleConfirm}
                  disabled={isLoading || !canConfirm}
                  className={cleanup ? 'bg-red-600 hover:bg-red-500 gap-2' : 'bg-amber-600 hover:bg-amber-500 gap-2'}
                >
                  {isLoading ? (
                    <>
                      <Loader2 className="w-4 h-4 animate-spin" />
                      {isFreeOnly ? t('pushDialog.freeingLoading') : cleanup ? t('pushDialog.backupAndCleanLoading') : t('pushDialog.backupLoading')}
                    </>
                  ) : isFreeOnly ? (
                    <>
                      <Trash2 className="w-4 h-4" />
                      {t('pushDialog.freeLocalSpace')}
                    </>
                  ) : cleanup ? (
                    <>
                      <ArrowUp className="w-4 h-4" />
                      <Trash2 className="w-3 h-3" />
                      {t('pushDialog.backupAndFree')}
                    </>
                  ) : (
                    <>
                      <ArrowUp className="w-4 h-4" />
                      {t('pushDialog.backupNow')}
                    </>
                  )}
                </Button>
              </>
            )}

            {showProgress && isRunning && (
              <Button variant="ghost" size="sm" onClick={cancel} leftIcon={<X className="w-4 h-4" />}>
                {t('common.cancel')}
              </Button>
            )}

            {showProgress && hasFailed && !isRunning && progress?.can_resume && (
              <Button
                variant="secondary"
                size="sm"
                onClick={() => {
                  const fn = cleanupPhase ? deleteFn : backupFn
                  if (fn) retryFailed(fn)
                }}
                leftIcon={<RotateCcw className="w-4 h-4" />}
              >
                {t('pushDialog.retryFailed', { count: failedItems })}
              </Button>
            )}

            {showProgress && (isCompleted || (isFailed && !progress?.can_resume)) && (
              <Button variant="primary" size="sm" onClick={handleClose}>
                {t('pushDialog.done')}
              </Button>
            )}
          </div>
        </div>
      </div>
    </div>
  )
}
