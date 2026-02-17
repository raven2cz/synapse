import { useEffect } from 'react'
import { useTranslation } from 'react-i18next'
import {
  X,
  ArrowDown,
  Info,
  Loader2,
  CheckCircle,
  XCircle,
  RotateCcw,
} from 'lucide-react'
import { Button } from '@/components/ui/Button'
import { formatBytes } from '@/lib/utils/format'
import { clsx } from 'clsx'
import { useTransferOperation, type TransferOperationItem } from '../inventory/useTransferOperation'
import type { PackBlobStatus } from '../inventory/types'

interface PullConfirmDialogProps {
  isOpen: boolean
  onClose: () => void
  onConfirm: () => void
  onComplete?: () => void
  packName: string
  blobs: PackBlobStatus[]
  isLoading?: boolean
  restoreFn?: (sha256: string) => Promise<void>
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
 * Confirmation dialog for pulling (restoring) pack blobs from backup.
 * Shows real-time progress after user confirms.
 */
export function PullConfirmDialog({
  isOpen,
  onClose,
  onConfirm,
  onComplete,
  packName,
  blobs,
  isLoading = false,
  restoreFn,
}: PullConfirmDialogProps) {
  const { t } = useTranslation()

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
    operation: 'restore',
    onComplete: () => {
      onComplete?.()
    },
  })

  // Reset state when dialog closes
  useEffect(() => {
    if (!isOpen) {
      reset()
    }
  }, [isOpen, reset])

  if (!isOpen) return null

  // Filter to backup-only blobs
  const blobsToRestore = blobs.filter(b => b.location === 'backup_only')
  const totalBytes = blobsToRestore.reduce((sum, b) => sum + b.size_bytes, 0)

  // Calculate progress values
  const transferredBytes = progress?.transferred_bytes || 0
  const completedItems = progress?.completed_items || 0
  const failedItems = progress?.failed_items || 0
  const totalItems = progress?.total_items || blobsToRestore.length
  // Force 100% when completed (progress might not update in time for fast operations)
  const progressPercent = isCompleted ? 100 : (totalBytes > 0 ? (transferredBytes / totalBytes) * 100 : 0)
  const bytesPerSecond = progress?.bytes_per_second || 0
  const etaSeconds = progress?.eta_seconds
  const elapsedSeconds = progress?.elapsed_seconds || 0

  // Show progress view if operation has started
  const showProgress = progress !== null || isRunning

  const handleConfirm = async () => {
    if (!restoreFn) {
      // Fallback to legacy behavior if restoreFn not provided
      onConfirm()
      return
    }

    // Convert blobs to TransferOperationItems
    const items: TransferOperationItem[] = blobsToRestore.map(blob => ({
      sha256: blob.sha256,
      display_name: blob.display_name,
      size_bytes: blob.size_bytes,
    }))

    await start(items, restoreFn)
  }

  const handleClose = () => {
    if (isRunning) {
      cancel()
    }
    onClose()
  }

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
        <div className="bg-gradient-to-r from-blue-500/20 to-cyan-500/20 border-b border-blue-500/30 p-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <div className="p-2 bg-blue-500/20 rounded-xl">
                <ArrowDown className="w-6 h-6 text-blue-400" />
              </div>
              <div>
                <h2 className="text-lg font-bold text-text-primary">{t('pullDialog.title')}</h2>
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
              <p className="text-text-secondary">
                {t('pullDialog.restoreBlobs', { count: blobsToRestore.length })}
              </p>

              {/* Blob list */}
              <div className="max-h-48 overflow-y-auto space-y-2 bg-slate-dark/50 rounded-xl p-3">
                {blobsToRestore.map(blob => (
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
                <span className="text-text-muted">{t('pullDialog.total')}</span>
                <span className="font-bold text-text-primary">{formatBytes(totalBytes)}</span>
              </div>

              {/* Info */}
              <div className="flex items-start gap-2 p-3 bg-blue-500/10 rounded-xl text-sm">
                <Info className="w-4 h-4 text-blue-400 flex-shrink-0 mt-0.5" />
                <span className="text-blue-300">
                  {t('pullDialog.profileNote')}
                </span>
              </div>
            </>
          ) : (
            // Progress view
            <>
              {/* Progress Bar */}
              <div className="space-y-2">
                <div className="flex justify-between text-sm">
                  <span className="text-text-secondary">
                    {isCompleted
                      ? t('pullDialog.restored', { count: completedItems })
                      : isFailed
                        ? t('pullDialog.completedAndFailed', { count: completedItems, count2: failedItems })
                        : t('pullDialog.restoring')}
                  </span>
                  <span className="text-text-primary font-medium">{progressPercent.toFixed(0)}%</span>
                </div>

                <div className="h-3 bg-slate-mid/50 rounded-full overflow-hidden">
                  <div
                    className={clsx(
                      'h-full rounded-full transition-all duration-300',
                      isCompleted && 'bg-gradient-to-r from-green-500 to-green-400',
                      isFailed && 'bg-gradient-to-r from-red-500 to-red-400',
                      !isCompleted && !isFailed && 'bg-gradient-to-r from-blue-500 to-cyan-400'
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
                      {etaSeconds !== undefined && etaSeconds > 0 && ` · ${t('pullDialog.remaining', { duration: formatDuration(etaSeconds) })}`}
                    </span>
                  )}
                  {isCompleted && elapsedSeconds > 0 && <span>{t('pullDialog.completedIn', { duration: formatDuration(elapsedSeconds) })}</span>}
                </div>
              </div>

              {/* Current File (when running) */}
              {isRunning && progress?.current_item && (
                <div className="bg-slate-mid/20 rounded-lg px-4 py-3">
                  <div className="flex items-center gap-2">
                    <Loader2 className="w-4 h-4 text-blue-400 animate-spin flex-shrink-0" />
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
                  {t('pullDialog.processing', { current: completedItems + failedItems + 1, total: totalItems })}
                </div>
              )}

              {/* Status Messages */}
              {isCompleted && !hasFailed && (
                <div className="flex items-center gap-3 bg-green-500/10 border border-green-500/30 rounded-lg px-4 py-3">
                  <CheckCircle className="w-5 h-5 text-green-400 flex-shrink-0" />
                  <span className="text-sm text-green-400">
                    {t('pullDialog.successRestore', { count: completedItems })}
                  </span>
                </div>
              )}

              {hasFailed && (
                <div className="bg-red-500/10 border border-red-500/30 rounded-lg px-4 py-3">
                  <div className="flex items-center gap-3">
                    <XCircle className="w-5 h-5 text-red-400 flex-shrink-0" />
                    <div className="flex-1">
                      <span className="text-sm text-red-400">
                        {t('pullDialog.filesFailed', { count: failedItems })}
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
                        <div className="text-xs text-red-400/60">{t('pullDialog.moreErrors', { count: progress.errors.length - 5 })}</div>
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
            {showProgress ? t('pullDialog.filesProgress', { completed: completedItems, total: totalItems }) : t('pullDialog.filesInfo', { count: blobsToRestore.length, size: formatBytes(totalBytes) })}
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
                  disabled={isLoading || blobsToRestore.length === 0}
                  className="bg-blue-600 hover:bg-blue-500 gap-2"
                >
                  {isLoading ? (
                    <>
                      <Loader2 className="w-4 h-4 animate-spin" />
                      {t('pullDialog.restoring')}
                    </>
                  ) : (
                    <>
                      <ArrowDown className="w-4 h-4" />
                      {t('pullDialog.restoreFromBackup')}
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

            {showProgress && hasFailed && !isRunning && progress?.can_resume && restoreFn && (
              <Button
                variant="secondary"
                size="sm"
                onClick={() => retryFailed(restoreFn)}
                leftIcon={<RotateCcw className="w-4 h-4" />}
              >
                {t('pullDialog.retryFailed', { count: failedItems })}
              </Button>
            )}

            {showProgress && (isCompleted || (isFailed && !progress?.can_resume)) && (
              <Button variant="primary" size="sm" onClick={handleClose}>
                {t('pullDialog.done')}
              </Button>
            )}
          </div>
        </div>
      </div>
    </div>
  )
}
