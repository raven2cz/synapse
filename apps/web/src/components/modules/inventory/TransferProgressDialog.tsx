/**
 * TransferProgressDialog - Shows progress for file transfer operations
 *
 * Features:
 * - Real-time progress bar with bytes transferred
 * - Current file being processed
 * - Transfer speed and ETA
 * - Error handling with retry capability
 * - Cancellation support
 * - Resumable transfers
 */
import { useState, useEffect, useCallback, useRef } from 'react'
import { useTranslation } from 'react-i18next'
import { clsx } from 'clsx'
import {
  X,
  Upload,
  Download,
  Trash2,
  Shield,
  CheckCircle,
  XCircle,
  AlertTriangle,
  Loader2,
  RotateCcw,
} from 'lucide-react'
import { Button } from '../../ui/Button'
import { formatBytes } from './utils'
import type { TransferProgress, TransferOperation, TransferStatus } from './types'

interface TransferProgressDialogProps {
  isOpen: boolean
  onClose: () => void
  operation: TransferOperation
  title: string
  items: Array<{ sha256: string; display_name: string; size_bytes: number }>
  onExecute: (
    items: string[],
    onProgress: (progress: TransferProgress) => void
  ) => Promise<TransferProgress>
  onCancel?: () => void
}

// Operation configs (visual only - text is translated via i18n)
const OPERATION_CONFIGS: Record<
  TransferOperation,
  { icon: React.ReactNode; color: string }
> = {
  backup: {
    icon: <Upload className="w-5 h-5" />,
    color: 'text-synapse',
  },
  restore: {
    icon: <Download className="w-5 h-5" />,
    color: 'text-blue-400',
  },
  download: {
    icon: <Download className="w-5 h-5" />,
    color: 'text-green-400',
  },
  cleanup: {
    icon: <Trash2 className="w-5 h-5" />,
    color: 'text-amber-400',
  },
  verify: {
    icon: <Shield className="w-5 h-5" />,
    color: 'text-purple-400',
  },
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

export function TransferProgressDialog({
  isOpen,
  onClose,
  operation,
  title,
  items,
  onExecute,
  onCancel,
}: TransferProgressDialogProps) {
  const { t } = useTranslation()
  const [progress, setProgress] = useState<TransferProgress | null>(null)
  const [isRunning, setIsRunning] = useState(false)
  const [showDetails, setShowDetails] = useState(false)
  const startTimeRef = useRef<number | null>(null)
  const abortRef = useRef(false)

  const config = OPERATION_CONFIGS[operation]

  // Calculate totals
  const totalBytes = items.reduce((sum, item) => sum + item.size_bytes, 0)
  const totalItems = items.length

  // Progress values
  const transferredBytes = progress?.transferred_bytes || 0
  const completedItems = progress?.completed_items || 0
  const failedItems = progress?.failed_items || 0
  const progressPercent = totalBytes > 0 ? (transferredBytes / totalBytes) * 100 : 0

  // Speed and ETA calculation
  const elapsedSeconds = progress?.elapsed_seconds || 0
  const bytesPerSecond = progress?.bytes_per_second || 0
  const etaSeconds = progress?.eta_seconds

  // Status checks
  const isCompleted = progress?.status === 'completed'
  const isFailed = progress?.status === 'failed'
  const hasFailed = failedItems > 0

  // Start transfer
  const startTransfer = useCallback(async () => {
    setIsRunning(true)
    abortRef.current = false
    startTimeRef.current = Date.now()

    // Initialize progress
    const initialProgress: TransferProgress = {
      operation,
      status: 'in_progress',
      total_items: totalItems,
      completed_items: 0,
      failed_items: 0,
      total_bytes: totalBytes,
      transferred_bytes: 0,
      items: items.map((item) => ({
        ...item,
        status: 'pending' as TransferStatus,
      })),
      errors: [],
      can_resume: true,
    }
    setProgress(initialProgress)

    try {
      const result = await onExecute(
        items.map((i) => i.sha256),
        (p) => {
          if (!abortRef.current) {
            setProgress(p)
          }
        }
      )
      setProgress(result)
    } catch (error) {
      setProgress((prev) =>
        prev
          ? {
              ...prev,
              status: 'failed',
              errors: [...prev.errors, error instanceof Error ? error.message : 'Unknown error'],
            }
          : null
      )
    } finally {
      setIsRunning(false)
    }
  }, [items, onExecute, operation, totalBytes, totalItems])

  // Auto-start when dialog opens
  useEffect(() => {
    if (isOpen && !progress && !isRunning) {
      startTransfer()
    }
  }, [isOpen, progress, isRunning, startTransfer])

  // Reset when closed
  useEffect(() => {
    if (!isOpen) {
      setProgress(null)
      setIsRunning(false)
      setShowDetails(false)
      abortRef.current = false
    }
  }, [isOpen])

  // Handle cancel
  const handleCancel = () => {
    abortRef.current = true
    setProgress((prev) => (prev ? { ...prev, status: 'cancelled' } : null))
    setIsRunning(false)
    onCancel?.()
  }

  // Handle retry failed
  const handleRetryFailed = useCallback(async () => {
    if (!progress) return

    const failedSha256s = progress.items
      .filter((item) => item.status === 'failed')
      .map((item) => item.sha256)

    if (failedSha256s.length === 0) return

    setIsRunning(true)
    abortRef.current = false

    // Reset failed items to pending
    setProgress((prev) =>
      prev
        ? {
            ...prev,
            status: 'in_progress',
            failed_items: 0,
            items: prev.items.map((item) =>
              item.status === 'failed' ? { ...item, status: 'pending' as TransferStatus, error: undefined } : item
            ),
            errors: [],
          }
        : null
    )

    try {
      const result = await onExecute(failedSha256s, (p) => {
        if (!abortRef.current) {
          // Merge with existing progress
          setProgress((prev) =>
            prev
              ? {
                  ...prev,
                  ...p,
                  completed_items: prev.completed_items - failedSha256s.length + p.completed_items,
                  transferred_bytes:
                    prev.transferred_bytes -
                    progress.items
                      .filter((i) => failedSha256s.includes(i.sha256))
                      .reduce((sum, i) => sum + (i.bytes_transferred || 0), 0) +
                    p.transferred_bytes,
                }
              : p
          )
        }
      })

      // Update final status
      setProgress((prev) =>
        prev
          ? {
              ...prev,
              status: result.failed_items > 0 ? 'failed' : 'completed',
              failed_items: result.failed_items,
              errors: result.errors,
            }
          : null
      )
    } catch (error) {
      setProgress((prev) =>
        prev
          ? {
              ...prev,
              status: 'failed',
              errors: [...prev.errors, error instanceof Error ? error.message : 'Unknown error'],
            }
          : null
      )
    } finally {
      setIsRunning(false)
    }
  }, [progress, onExecute])

  if (!isOpen) return null

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center">
      {/* Backdrop */}
      <div
        className="absolute inset-0 bg-obsidian/80 backdrop-blur-sm"
        onClick={isCompleted || isFailed ? onClose : undefined}
      />

      {/* Dialog */}
      <div className="relative bg-slate-deep border border-slate-mid/50 rounded-2xl shadow-2xl w-full max-w-lg mx-4 overflow-hidden">
        {/* Header */}
        <div className="flex items-center justify-between px-5 py-4 border-b border-slate-mid/30">
          <div className="flex items-center gap-3">
            <div className={clsx('p-2 rounded-lg bg-slate-mid/30', config.color)}>{config.icon}</div>
            <div>
              <h2 className="text-lg font-semibold text-text-primary">{title}</h2>
              <p className="text-sm text-text-muted">
                {t('inventory.transfer.filesCount', { count: totalItems })} &middot; {formatBytes(totalBytes)}
              </p>
            </div>
          </div>

          {(isCompleted || isFailed) && (
            <button
              onClick={onClose}
              className="p-2 rounded-lg hover:bg-slate-mid/50 text-text-muted hover:text-text-primary transition-colors"
            >
              <X className="w-5 h-5" />
            </button>
          )}
        </div>

        {/* Content */}
        <div className="p-5 space-y-4">
          {/* Progress Bar */}
          <div className="space-y-2">
            <div className="flex justify-between text-sm">
              <span className="text-text-secondary">
                {isCompleted
                  ? t(`inventory.transfer.completed.${operation}`, { count: completedItems })
                  : isFailed
                    ? t('inventory.transfer.completedAndFailed', { completed: completedItems, failed: failedItems })
                    : t(`inventory.transfer.running.${operation}`)}
              </span>
              <span className="text-text-primary font-medium">{progressPercent.toFixed(0)}%</span>
            </div>

            <div className="h-3 bg-slate-mid/50 rounded-full overflow-hidden">
              <div
                className={clsx(
                  'h-full rounded-full transition-all duration-300',
                  isCompleted && 'bg-gradient-to-r from-green-500 to-green-400',
                  isFailed && 'bg-gradient-to-r from-red-500 to-red-400',
                  !isCompleted && !isFailed && 'bg-gradient-to-r from-synapse to-pulse'
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
                  {etaSeconds !== undefined && ` \u2022 ${t('inventory.transfer.remaining', { duration: formatDuration(etaSeconds) })}`}
                </span>
              )}
              {isCompleted && elapsedSeconds > 0 && (
                <span>{t('inventory.transfer.completedIn', { duration: formatDuration(elapsedSeconds) })}</span>
              )}
            </div>
          </div>

          {/* Current File (when running) */}
          {isRunning && progress?.current_item && (
            <div className="bg-slate-mid/20 rounded-lg px-4 py-3">
              <div className="flex items-center gap-2">
                <Loader2 className="w-4 h-4 text-synapse animate-spin" />
                <span className="text-sm text-text-secondary truncate flex-1">
                  {progress.current_item.display_name}
                </span>
                <span className="text-xs text-text-muted">
                  {formatBytes(progress.current_item.size_bytes)}
                </span>
              </div>
            </div>
          )}

          {/* Status Messages */}
          {isCompleted && !hasFailed && (
            <div className="flex items-center gap-3 bg-green-500/10 border border-green-500/30 rounded-lg px-4 py-3">
              <CheckCircle className="w-5 h-5 text-green-400 flex-shrink-0" />
              <span className="text-sm text-green-400">
                {t(`inventory.transfer.success.${operation}`, { count: completedItems })}
              </span>
            </div>
          )}

          {hasFailed && (
            <div className="bg-red-500/10 border border-red-500/30 rounded-lg px-4 py-3">
              <div className="flex items-center gap-3">
                <XCircle className="w-5 h-5 text-red-400 flex-shrink-0" />
                <div className="flex-1">
                  <span className="text-sm text-red-400">
                    {t('inventory.transfer.filesFailed', { count: failedItems })}
                  </span>
                  {progress?.errors && progress.errors.length > 0 && (
                    <button
                      onClick={() => setShowDetails(!showDetails)}
                      className="text-xs text-red-400/70 hover:text-red-400 ml-2 underline"
                    >
                      {showDetails ? t('inventory.transfer.hideDetails') : t('inventory.transfer.showDetails')}
                    </button>
                  )}
                </div>
              </div>

              {showDetails && progress?.errors && progress.errors.length > 0 && (
                <div className="mt-3 pt-3 border-t border-red-500/20 space-y-1 max-h-32 overflow-y-auto">
                  {progress.errors.map((error, i) => (
                    <div key={i} className="text-xs text-red-400/80 font-mono">
                      {error}
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}

          {/* Space Warning */}
          {progress?.can_resume === false && (
            <div className="flex items-center gap-3 bg-amber-500/10 border border-amber-500/30 rounded-lg px-4 py-3">
              <AlertTriangle className="w-5 h-5 text-amber-400 flex-shrink-0" />
              <span className="text-sm text-amber-400">
                {t('inventory.transfer.notEnoughSpace')}
              </span>
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="flex items-center justify-between px-5 py-4 border-t border-slate-mid/30 bg-slate-mid/10">
          <div className="text-xs text-text-muted">
            {t('inventory.transfer.filesProgress', { completed: completedItems, total: totalItems })}
          </div>

          <div className="flex gap-2">
            {isRunning && (
              <Button variant="ghost" size="sm" onClick={handleCancel} leftIcon={<X className="w-4 h-4" />}>
                {t('common.cancel')}
              </Button>
            )}

            {hasFailed && !isRunning && progress?.can_resume && (
              <Button
                variant="secondary"
                size="sm"
                onClick={handleRetryFailed}
                leftIcon={<RotateCcw className="w-4 h-4" />}
              >
                {t('inventory.transfer.retryFailed', { count: failedItems })}
              </Button>
            )}

            {(isCompleted || (isFailed && !progress?.can_resume)) && (
              <Button variant="primary" size="sm" onClick={onClose}>
                {t('inventory.transfer.done')}
              </Button>
            )}
          </div>
        </div>
      </div>
    </div>
  )
}
