/**
 * TransferProgressModal - Unified modal for showing transfer operation progress
 *
 * Uses useTransferOperation hook for consistent progress tracking.
 * Can be used for backup, restore, sync, delete, and verify operations.
 */
import { useEffect } from 'react'
import { createPortal } from 'react-dom'
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
  ArrowUpDown,
} from 'lucide-react'
import { Button } from '../../ui/Button'
import { formatBytes } from './utils'
import { useTransferOperation, type TransferOperationItem } from './useTransferOperation'
import type { TransferOperation } from './types'

// Operation configs
const OPERATION_CONFIGS: Record<
  TransferOperation | 'sync',
  { icon: React.ReactNode; color: string; bgColor: string; verb: string; verbPast: string }
> = {
  backup: {
    icon: <Upload className="w-5 h-5" />,
    color: 'text-synapse',
    bgColor: 'bg-synapse/20',
    verb: 'Backing up',
    verbPast: 'backed up',
  },
  restore: {
    icon: <Download className="w-5 h-5" />,
    color: 'text-blue-400',
    bgColor: 'bg-blue-500/20',
    verb: 'Restoring',
    verbPast: 'restored',
  },
  download: {
    icon: <Download className="w-5 h-5" />,
    color: 'text-green-400',
    bgColor: 'bg-green-500/20',
    verb: 'Downloading',
    verbPast: 'downloaded',
  },
  cleanup: {
    icon: <Trash2 className="w-5 h-5" />,
    color: 'text-amber-400',
    bgColor: 'bg-amber-500/20',
    verb: 'Cleaning up',
    verbPast: 'cleaned up',
  },
  verify: {
    icon: <Shield className="w-5 h-5" />,
    color: 'text-purple-400',
    bgColor: 'bg-purple-500/20',
    verb: 'Verifying',
    verbPast: 'verified',
  },
  sync: {
    icon: <ArrowUpDown className="w-5 h-5" />,
    color: 'text-cyan-400',
    bgColor: 'bg-cyan-500/20',
    verb: 'Syncing',
    verbPast: 'synced',
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

export interface TransferProgressModalProps {
  isOpen: boolean
  onClose: () => void
  operation: TransferOperation | 'sync'
  title: string
  items: TransferOperationItem[]
  executeFn: (sha256: string) => Promise<void>
  onComplete?: () => void
}

export function TransferProgressModal({
  isOpen,
  onClose,
  operation,
  title,
  items,
  executeFn,
  onComplete,
}: TransferProgressModalProps) {
  const { progress, isRunning, isCompleted, isFailed, hasFailed, start, cancel, retryFailed, reset } =
    useTransferOperation({
      operation: operation === 'sync' ? 'backup' : operation,
      onComplete: () => {
        onComplete?.()
      },
    })

  const config = OPERATION_CONFIGS[operation]

  // Auto-start when dialog opens
  useEffect(() => {
    if (isOpen && !progress && !isRunning && items.length > 0) {
      start(items, executeFn)
    }
  }, [isOpen, progress, isRunning, items, executeFn, start])

  // Reset when closed
  useEffect(() => {
    if (!isOpen) {
      reset()
    }
  }, [isOpen, reset])

  // Handle escape key
  useEffect(() => {
    if (!isOpen) return

    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape' && (isCompleted || isFailed)) {
        onClose()
      }
    }

    window.addEventListener('keydown', handleKeyDown)
    return () => window.removeEventListener('keydown', handleKeyDown)
  }, [isOpen, isCompleted, isFailed, onClose])

  if (!isOpen) return null

  // Calculate values
  const totalBytes = progress?.total_bytes || items.reduce((sum, i) => sum + i.size_bytes, 0)
  const totalItems = progress?.total_items || items.length
  const transferredBytes = progress?.transferred_bytes || 0
  const completedItems = progress?.completed_items || 0
  const failedItems = progress?.failed_items || 0
  const progressPercent = totalBytes > 0 ? (transferredBytes / totalBytes) * 100 : 0
  const bytesPerSecond = progress?.bytes_per_second || 0
  const etaSeconds = progress?.eta_seconds
  const elapsedSeconds = progress?.elapsed_seconds || 0

  const modalContent = (
    <div className="fixed inset-0 z-[100] flex items-center justify-center">
      {/* Backdrop */}
      <div
        className="absolute inset-0 bg-black/80 backdrop-blur-sm"
        onClick={isCompleted || isFailed ? onClose : undefined}
      />

      {/* Dialog */}
      <div
        className={clsx(
          'relative w-full max-w-lg m-4',
          'bg-slate-dark/95 backdrop-blur-xl',
          'border border-slate-mid/50 rounded-2xl shadow-2xl',
          'animate-in fade-in zoom-in-95 duration-200'
        )}
      >
        {/* Header */}
        <div className="flex items-center justify-between px-5 py-4 border-b border-slate-mid/30">
          <div className="flex items-center gap-3">
            <div className={clsx('p-2 rounded-lg', config.bgColor, config.color)}>{config.icon}</div>
            <div>
              <h2 className="text-lg font-semibold text-text-primary">{title}</h2>
              <p className="text-sm text-text-muted">
                {totalItems} file{totalItems !== 1 ? 's' : ''} &middot; {formatBytes(totalBytes)}
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
                  ? `${completedItems} ${config.verbPast}`
                  : isFailed
                    ? `${completedItems} completed, ${failedItems} failed`
                    : `${config.verb}...`}
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
                  {etaSeconds !== undefined && etaSeconds > 0 && ` · ${formatDuration(etaSeconds)} remaining`}
                </span>
              )}
              {isCompleted && elapsedSeconds > 0 && <span>Completed in {formatDuration(elapsedSeconds)}</span>}
            </div>
          </div>

          {/* Current File (when running) */}
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

          {/* Item counter during processing */}
          {isRunning && (
            <div className="text-sm text-text-muted text-center">
              Processing {completedItems + failedItems + 1} of {totalItems}...
            </div>
          )}

          {/* Status Messages */}
          {isCompleted && !hasFailed && (
            <div className="flex items-center gap-3 bg-green-500/10 border border-green-500/30 rounded-lg px-4 py-3">
              <CheckCircle className="w-5 h-5 text-green-400 flex-shrink-0" />
              <span className="text-sm text-green-400">
                Successfully {config.verbPast} {completedItems} file{completedItems !== 1 ? 's' : ''}
              </span>
            </div>
          )}

          {hasFailed && (
            <div className="bg-red-500/10 border border-red-500/30 rounded-lg px-4 py-3">
              <div className="flex items-center gap-3">
                <XCircle className="w-5 h-5 text-red-400 flex-shrink-0" />
                <div className="flex-1">
                  <span className="text-sm text-red-400">
                    {failedItems} file{failedItems !== 1 ? 's' : ''} failed
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
                    <div className="text-xs text-red-400/60">...and {progress.errors.length - 5} more</div>
                  )}
                </div>
              )}
            </div>
          )}

          {/* Space Warning */}
          {progress?.can_resume === false && isFailed && (
            <div className="flex items-center gap-3 bg-amber-500/10 border border-amber-500/30 rounded-lg px-4 py-3">
              <AlertTriangle className="w-5 h-5 text-amber-400 flex-shrink-0" />
              <span className="text-sm text-amber-400">
                Not enough space on target. Free up space and try again.
              </span>
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="flex items-center justify-between px-5 py-4 border-t border-slate-mid/30 bg-slate-mid/10">
          <div className="text-xs text-text-muted">
            {completedItems}/{totalItems} files
          </div>

          <div className="flex gap-2">
            {isRunning && (
              <Button variant="ghost" size="sm" onClick={cancel} leftIcon={<X className="w-4 h-4" />}>
                Cancel
              </Button>
            )}

            {hasFailed && !isRunning && progress?.can_resume && (
              <Button
                variant="secondary"
                size="sm"
                onClick={() => retryFailed(executeFn)}
                leftIcon={<RotateCcw className="w-4 h-4" />}
              >
                Retry Failed ({failedItems})
              </Button>
            )}

            {(isCompleted || (isFailed && !progress?.can_resume)) && (
              <Button variant="primary" size="sm" onClick={onClose}>
                Done
              </Button>
            )}
          </div>
        </div>
      </div>
    </div>
  )

  return createPortal(modalContent, document.body)
}
