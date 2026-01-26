/**
 * BackupSyncWizard - Wizard for Backup/Restore Operations
 *
 * Handles bulk sync operations between local and backup storage.
 * Uses useTransferOperation for real-time progress tracking.
 *
 * Steps:
 * 1. Preview - Dry run to show what will be synced
 * 2. Progress - Show sync progress with real-time updates
 * 3. Complete - Show results
 */
import { useState, useEffect, useCallback } from 'react'
import { createPortal } from 'react-dom'
import { clsx } from 'clsx'
import {
  X,
  Upload,
  Download,
  CheckCircle,
  Loader2,
  AlertTriangle,
  HardDrive,
  Cloud,
  XCircle,
  RotateCcw,
} from 'lucide-react'
import { Button } from '../../ui/Button'
import { Card } from '../../ui/Card'
import { AssetKindIcon, getKindLabel } from './AssetKindIcon'
import { formatBytes } from './utils'
import { useTransferOperation } from './useTransferOperation'
import type { SyncResult, SyncItem } from './types'

interface BackupSyncWizardProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  direction: 'to_backup' | 'from_backup'
  onPreview: () => Promise<SyncResult>
  onExecute: () => Promise<SyncResult>
  /** Execute function for individual blob - for real-time progress */
  onExecuteBlob?: (sha256: string) => Promise<void>
  onComplete: () => void
}

type WizardStep = 'preview' | 'syncing' | 'complete'

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

export function BackupSyncWizard({
  open,
  onOpenChange,
  direction,
  onPreview,
  onExecute,
  onExecuteBlob,
  onComplete,
}: BackupSyncWizardProps) {
  const [step, setStep] = useState<WizardStep>('preview')
  const [isLoadingPreview, setIsLoadingPreview] = useState(false)
  const [previewResult, setPreviewResult] = useState<SyncResult | null>(null)
  const [error, setError] = useState<string | null>(null)

  const isToBackup = direction === 'to_backup'

  // Transfer operation hook for real-time progress
  const {
    progress,
    isRunning,
    isCompleted,
    isFailed,
    hasFailed,
    start,
    cancel,
    retryFailed,
    reset: resetTransfer,
  } = useTransferOperation({
    operation: isToBackup ? 'backup' : 'restore',
    onComplete: () => {
      setStep('complete')
    },
  })

  // Load preview when dialog opens
  useEffect(() => {
    if (open) {
      setStep('preview')
      setPreviewResult(null)
      setError(null)
      resetTransfer()
      loadPreview()
    }
  }, [open, resetTransfer])

  const loadPreview = async () => {
    setIsLoadingPreview(true)
    setError(null)
    try {
      const result = await onPreview()
      setPreviewResult(result)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load preview')
    } finally {
      setIsLoadingPreview(false)
    }
  }

  // Handle escape key
  useEffect(() => {
    if (!open) return

    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape' && !isRunning && step !== 'syncing') {
        handleClose()
      }
    }

    window.addEventListener('keydown', handleKeyDown)
    return () => window.removeEventListener('keydown', handleKeyDown)
  }, [open, isRunning, step])

  // Execute function - either per-blob with progress or bulk
  const executeBlob = useCallback(
    async (sha256: string) => {
      if (onExecuteBlob) {
        return onExecuteBlob(sha256)
      }
      // Fallback: no per-blob execute, throw to show we need it
      throw new Error('Per-blob execute not provided')
    },
    [onExecuteBlob]
  )

  const handleSync = async () => {
    if (!previewResult || previewResult.items.length === 0) return

    setStep('syncing')
    setError(null)

    if (onExecuteBlob) {
      // Use transfer operation for real-time progress
      const items = previewResult.items.map((item) => ({
        sha256: item.sha256,
        display_name: item.display_name,
        size_bytes: item.size_bytes,
      }))

      await start(items, executeBlob)
    } else {
      // Fallback to bulk execute (no real-time progress)
      try {
        await onExecute()
        setStep('complete')
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Sync failed')
        setStep('preview')
      }
    }
  }

  const handleClose = () => {
    if (step === 'complete' || isCompleted) {
      onComplete()
    }
    onOpenChange(false)
  }

  const handleRetry = () => {
    retryFailed(executeBlob)
  }

  if (!open) return null

  // Calculate progress values
  const totalItems = previewResult?.items.length || 0
  const totalBytes = previewResult?.bytes_to_sync || 0
  const completedItems = progress?.completed_items || 0
  const failedItems = progress?.failed_items || 0
  const transferredBytes = progress?.transferred_bytes || 0
  const progressPercent = totalBytes > 0 ? (transferredBytes / totalBytes) * 100 : 0
  const bytesPerSecond = progress?.bytes_per_second || 0
  const etaSeconds = progress?.eta_seconds
  const elapsedSeconds = progress?.elapsed_seconds || 0

  const dialogContent = (
    <div className="fixed inset-0 z-[100] flex items-center justify-center">
      {/* Backdrop */}
      <div
        className="absolute inset-0 bg-black/80 backdrop-blur-sm"
        onClick={!isRunning && step !== 'syncing' ? handleClose : undefined}
      />

      {/* Dialog */}
      <div
        className={clsx(
          'relative w-full max-w-2xl m-4',
          'bg-slate-dark/95 backdrop-blur-xl',
          'border border-slate-mid/50 rounded-2xl shadow-2xl',
          'flex flex-col max-h-[85vh]',
          'animate-in fade-in zoom-in-95 duration-200'
        )}
      >
        {/* Header */}
        <div className="flex items-center justify-between p-6 border-b border-slate-mid/30">
          <div className="flex items-center gap-3">
            <div className={clsx('p-2 rounded-xl', isToBackup ? 'bg-blue-500/20' : 'bg-green-500/20')}>
              {isToBackup ? (
                <Upload className="w-6 h-6 text-blue-500" />
              ) : (
                <Download className="w-6 h-6 text-green-500" />
              )}
            </div>
            <div>
              <h2 className="text-xl font-bold text-text-primary">
                {isToBackup ? 'Backup to External Storage' : 'Restore from Backup'}
              </h2>
              <p className="text-sm text-text-muted">
                {isToBackup
                  ? 'Copy local-only blobs to backup storage'
                  : 'Restore backup-only blobs to local storage'}
              </p>
            </div>
          </div>

          <button
            onClick={handleClose}
            disabled={isRunning}
            className={clsx(
              'p-2 rounded-xl transition-colors',
              'hover:bg-white/10',
              isRunning && 'opacity-50 cursor-not-allowed'
            )}
          >
            <X className="w-6 h-6 text-text-muted" />
          </button>
        </div>

        {/* Content */}
        <div className="flex-1 overflow-y-auto p-6">
          {/* Error message */}
          {error && (
            <div className="flex items-start gap-3 p-4 mb-4 bg-red-500/10 border border-red-500/20 rounded-xl">
              <AlertTriangle className="w-5 h-5 text-red-500 flex-shrink-0 mt-0.5" />
              <div className="text-sm text-red-400">{error}</div>
            </div>
          )}

          {/* Loading preview */}
          {step === 'preview' && isLoadingPreview && (
            <div className="flex items-center justify-center py-16">
              <Loader2 className="w-8 h-8 animate-spin text-synapse" />
            </div>
          )}

          {/* Preview: No items to sync */}
          {step === 'preview' && !isLoadingPreview && previewResult?.blobs_to_sync === 0 && (
            <div className="text-center py-8">
              <div className="w-16 h-16 mx-auto mb-6 rounded-2xl bg-green-500/20 flex items-center justify-center">
                <CheckCircle className="w-8 h-8 text-green-500" />
              </div>
              <h3 className="text-lg font-medium text-text-primary mb-2">Already Synced!</h3>
              <p className="text-text-muted">
                {isToBackup
                  ? 'All local blobs are already backed up.'
                  : 'All backup blobs are already restored locally.'}
              </p>
            </div>
          )}

          {/* Preview: Items to sync */}
          {step === 'preview' && !isLoadingPreview && previewResult && previewResult.blobs_to_sync > 0 && (
            <div className="space-y-6">
              {/* Summary cards */}
              <div className="grid grid-cols-2 gap-4">
                <Card padding="md" className="text-center">
                  <div className="text-3xl font-bold text-text-primary">{previewResult.blobs_to_sync}</div>
                  <div className="text-sm text-text-muted mt-1">Blobs to {isToBackup ? 'backup' : 'restore'}</div>
                </Card>
                <Card padding="md" className="text-center">
                  <div className="text-3xl font-bold text-synapse">{formatBytes(previewResult.bytes_to_sync)}</div>
                  <div className="text-sm text-text-muted mt-1">Total size</div>
                </Card>
              </div>

              {/* Direction visualization */}
              <div className="flex items-center justify-center gap-4 py-4">
                <div className="flex items-center gap-2">
                  <HardDrive className={clsx('w-6 h-6', isToBackup ? 'text-synapse' : 'text-text-muted')} />
                  <span className="text-sm text-text-secondary">Local</span>
                </div>
                <div className="flex items-center gap-2">
                  {isToBackup ? (
                    <>
                      <div className="w-8 h-0.5 bg-blue-500" />
                      <Upload className="w-4 h-4 text-blue-500" />
                      <div className="w-8 h-0.5 bg-blue-500" />
                    </>
                  ) : (
                    <>
                      <div className="w-8 h-0.5 bg-green-500" />
                      <Download className="w-4 h-4 text-green-500" />
                      <div className="w-8 h-0.5 bg-green-500" />
                    </>
                  )}
                </div>
                <div className="flex items-center gap-2">
                  <Cloud className={clsx('w-6 h-6', isToBackup ? 'text-text-muted' : 'text-synapse')} />
                  <span className="text-sm text-text-secondary">Backup</span>
                </div>
              </div>

              {/* Items list */}
              <div>
                <h4 className="text-sm font-medium text-text-secondary mb-3">
                  Items to sync ({previewResult.items.length})
                </h4>
                <div className="max-h-48 overflow-y-auto border border-slate-mid/30 rounded-xl">
                  {previewResult.items.map((item) => (
                    <SyncItemRow key={item.sha256} item={item} />
                  ))}
                </div>
              </div>

              {/* Space warning */}
              {previewResult.space_warning && (
                <div className="flex items-start gap-3 p-4 bg-amber-500/10 border border-amber-500/20 rounded-xl">
                  <AlertTriangle className="w-5 h-5 text-amber-500 flex-shrink-0 mt-0.5" />
                  <div className="text-sm text-amber-400">{previewResult.space_warning}</div>
                </div>
              )}
            </div>
          )}

          {/* Syncing progress - REAL-TIME UPDATES */}
          {step === 'syncing' && (
            <div className="space-y-6">
              {/* Progress bar */}
              <div className="space-y-2">
                <div className="flex justify-between text-sm">
                  <span className="text-text-secondary">
                    {isCompleted
                      ? `${completedItems} ${isToBackup ? 'backed up' : 'restored'}`
                      : hasFailed
                        ? `${completedItems} completed, ${failedItems} failed`
                        : `${isToBackup ? 'Backing up' : 'Restoring'}...`}
                  </span>
                  <span className="text-text-primary font-medium">{progressPercent.toFixed(0)}%</span>
                </div>

                <div className="h-3 bg-slate-mid/50 rounded-full overflow-hidden">
                  <div
                    className={clsx(
                      'h-full rounded-full transition-all duration-300',
                      isCompleted && !hasFailed && 'bg-gradient-to-r from-green-500 to-green-400',
                      hasFailed && 'bg-gradient-to-r from-red-500 to-red-400',
                      !isCompleted && !hasFailed && 'bg-gradient-to-r from-synapse to-pulse'
                    )}
                    style={{ width: `${progressPercent}%` }}
                  />
                </div>

                <div className="flex justify-between text-xs text-text-muted">
                  <span>
                    {formatBytes(transferredBytes)} / {formatBytes(totalBytes)}
                  </span>
                  {isRunning && bytesPerSecond > 0 && (
                    <span>
                      {formatSpeed(bytesPerSecond)}
                      {etaSeconds !== undefined && etaSeconds > 0 && ` · ${formatDuration(etaSeconds)} remaining`}
                    </span>
                  )}
                  {isCompleted && elapsedSeconds > 0 && <span>Completed in {formatDuration(elapsedSeconds)}</span>}
                </div>
              </div>

              {/* Current file being processed */}
              {isRunning && progress?.current_item && (
                <div className="bg-slate-mid/20 rounded-lg px-4 py-3">
                  <div className="flex items-center gap-2">
                    <Loader2 className="w-4 h-4 text-synapse animate-spin flex-shrink-0" />
                    <span className="text-sm text-text-secondary truncate flex-1">
                      {progress.current_item.display_name}
                    </span>
                    <span className="text-xs text-text-muted flex-shrink-0">
                      {formatBytes(progress.current_item.size_bytes)}
                    </span>
                  </div>
                </div>
              )}

              {/* Item counter */}
              {isRunning && (
                <div className="text-sm text-text-muted text-center">
                  Processing {completedItems + failedItems + 1} of {totalItems}...
                </div>
              )}

              {/* Failed items */}
              {hasFailed && (
                <div className="bg-red-500/10 border border-red-500/30 rounded-lg px-4 py-3">
                  <div className="flex items-center gap-3">
                    <XCircle className="w-5 h-5 text-red-400 flex-shrink-0" />
                    <span className="text-sm text-red-400">
                      {failedItems} file{failedItems !== 1 ? 's' : ''} failed
                    </span>
                  </div>
                  {progress?.errors && progress.errors.length > 0 && (
                    <div className="mt-3 pt-3 border-t border-red-500/20 space-y-1 max-h-24 overflow-y-auto">
                      {progress.errors.slice(0, 3).map((err, i) => (
                        <div key={i} className="text-xs text-red-400/80 truncate">
                          {err}
                        </div>
                      ))}
                      {progress.errors.length > 3 && (
                        <div className="text-xs text-red-400/60">...and {progress.errors.length - 3} more</div>
                      )}
                    </div>
                  )}
                </div>
              )}
            </div>
          )}

          {/* Complete */}
          {step === 'complete' && isCompleted && !hasFailed && (
            <div className="text-center py-8">
              <div className="w-16 h-16 mx-auto mb-6 rounded-2xl bg-green-500/20 flex items-center justify-center">
                <CheckCircle className="w-8 h-8 text-green-500" />
              </div>
              <h3 className="text-xl font-bold text-text-primary mb-2">
                {isToBackup ? 'Backup Complete!' : 'Restore Complete!'}
              </h3>
              <p className="text-text-muted mb-6">
                Successfully synced {completedItems} blob{completedItems !== 1 ? 's' : ''}
              </p>

              <div className="inline-flex items-center gap-3 px-6 py-3 bg-green-500/10 border border-green-500/20 rounded-xl">
                {isToBackup ? (
                  <Cloud className="w-5 h-5 text-green-500" />
                ) : (
                  <HardDrive className="w-5 h-5 text-green-500" />
                )}
                <span className="text-lg font-medium text-green-400">{formatBytes(transferredBytes)} transferred</span>
              </div>

              {elapsedSeconds > 0 && (
                <p className="text-sm text-text-muted mt-4">Completed in {formatDuration(elapsedSeconds)}</p>
              )}
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="flex items-center justify-between px-5 py-4 border-t border-slate-mid/30">
          <div className="text-xs text-text-muted">
            {step === 'syncing' || step === 'complete' ? `${completedItems}/${totalItems} files` : ''}
          </div>

          <div className="flex gap-2">
            {step === 'preview' && (
              <>
                <Button variant="secondary" onClick={handleClose}>
                  Cancel
                </Button>
                {previewResult && previewResult.blobs_to_sync > 0 && (
                  <Button
                    variant="primary"
                    onClick={handleSync}
                    leftIcon={isToBackup ? <Upload className="w-4 h-4" /> : <Download className="w-4 h-4" />}
                  >
                    {isToBackup ? 'Start Backup' : 'Start Restore'}
                  </Button>
                )}
              </>
            )}

            {step === 'syncing' && isRunning && (
              <Button variant="ghost" size="sm" onClick={cancel} leftIcon={<X className="w-4 h-4" />}>
                Cancel
              </Button>
            )}

            {step === 'syncing' && hasFailed && !isRunning && (
              <Button
                variant="secondary"
                size="sm"
                onClick={handleRetry}
                leftIcon={<RotateCcw className="w-4 h-4" />}
              >
                Retry Failed ({failedItems})
              </Button>
            )}

            {(step === 'complete' || (step === 'syncing' && (isCompleted || (isFailed && !progress?.can_resume)))) && (
              <Button variant="primary" onClick={handleClose}>
                Close
              </Button>
            )}
          </div>
        </div>
      </div>
    </div>
  )

  return createPortal(dialogContent, document.body)
}

// Sync item row component
function SyncItemRow({ item }: { item: SyncItem }) {
  return (
    <div className="flex items-center justify-between p-3 border-b border-slate-mid/20 last:border-b-0 hover:bg-slate-deep/50">
      <div className="flex items-center gap-3 min-w-0">
        <AssetKindIcon kind={item.kind} />
        <div className="min-w-0">
          <div className="font-medium text-text-primary truncate">{item.display_name}</div>
          <div className="text-xs text-text-muted">{getKindLabel(item.kind)}</div>
        </div>
      </div>
      <div className="font-mono text-sm text-text-secondary">{formatBytes(item.size_bytes)}</div>
    </div>
  )
}
