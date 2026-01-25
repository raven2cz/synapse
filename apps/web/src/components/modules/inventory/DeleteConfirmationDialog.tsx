/**
 * DeleteConfirmationDialog - Guard Rails for Blob Deletion
 *
 * A critical safety component that prevents accidental data loss.
 * Features:
 * - Visual warning for last copy (no backup exists)
 * - Warning when blob is referenced by packs
 * - Different button styles based on danger level
 * - Clear messaging about what will happen
 */
import { useEffect } from 'react'
import { createPortal } from 'react-dom'
import { clsx } from 'clsx'
import { AlertTriangle, Trash2, Info, X, Shield, Cloud, HardDrive } from 'lucide-react'
import { Button } from '../../ui/Button'
import { formatBytes } from './utils'
import { AssetKindIcon, getKindLabel } from './AssetKindIcon'
import type { InventoryItem } from './types'

interface DeleteConfirmationDialogProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  item: InventoryItem | null
  target: 'local' | 'backup' | 'both'
  onConfirm: () => void
  isLoading?: boolean
}

export function DeleteConfirmationDialog({
  open,
  onOpenChange,
  item,
  target,
  onConfirm,
  isLoading = false,
}: DeleteConfirmationDialogProps) {
  // Handle escape key
  useEffect(() => {
    if (!open) return

    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape' && !isLoading) {
        onOpenChange(false)
      }
    }

    window.addEventListener('keydown', handleKeyDown)
    return () => window.removeEventListener('keydown', handleKeyDown)
  }, [open, isLoading, onOpenChange])

  if (!open || !item) return null

  // Determine warning levels
  const isLastCopy =
    target === 'both' ||
    (target === 'local' && !item.on_backup) ||
    (target === 'backup' && !item.on_local)

  const isReferenced = item.status === 'referenced'
  const hasHighRisk = isLastCopy && isReferenced

  // Get target label for UI
  const targetLabel = target === 'both' ? 'everywhere' : `from ${target}`

  const dialogContent = (
    <div className="fixed inset-0 z-[100] flex items-center justify-center">
      {/* Backdrop */}
      <div
        className="absolute inset-0 bg-black/80 backdrop-blur-sm"
        onClick={!isLoading ? () => onOpenChange(false) : undefined}
      />

      {/* Dialog */}
      <div
        className={clsx(
          'relative w-full max-w-md m-4',
          'bg-slate-dark/95 backdrop-blur-xl',
          'border rounded-2xl shadow-2xl',
          'animate-in fade-in zoom-in-95 duration-200',
          hasHighRisk
            ? 'border-red-500/50'
            : isLastCopy
              ? 'border-amber-500/50'
              : 'border-slate-mid/50'
        )}
      >
        {/* Header */}
        <div className="flex items-center justify-between p-6 border-b border-slate-mid/30">
          <div className="flex items-center gap-3">
            {isLastCopy ? (
              <div className="p-2 bg-red-500/20 rounded-xl">
                <AlertTriangle className="w-6 h-6 text-red-500" />
              </div>
            ) : (
              <div className="p-2 bg-slate-mid/30 rounded-xl">
                <Trash2 className="w-6 h-6 text-text-muted" />
              </div>
            )}
            <div>
              <h2 className="text-xl font-bold text-text-primary">
                {isLastCopy ? 'Delete Last Copy?' : 'Delete Blob?'}
              </h2>
              <p className="text-sm text-text-muted">
                {target === 'both' ? 'Remove from all locations' : `Delete ${targetLabel}`}
              </p>
            </div>
          </div>

          <button
            onClick={() => onOpenChange(false)}
            disabled={isLoading}
            className={clsx(
              'p-2 rounded-xl transition-colors',
              'hover:bg-white/10',
              isLoading && 'opacity-50 cursor-not-allowed'
            )}
          >
            <X className="w-6 h-6 text-text-muted" />
          </button>
        </div>

        {/* Content */}
        <div className="p-6 space-y-4">
          {/* Blob info */}
          <div className="bg-slate-deep/50 border border-slate-mid/30 p-4 rounded-xl">
            <div className="flex items-start gap-3">
              <AssetKindIcon kind={item.kind} size="lg" />
              <div className="flex-1 min-w-0">
                <div className="font-medium text-text-primary truncate">
                  {item.display_name}
                </div>
                <div className="flex items-center gap-3 text-sm text-text-muted mt-1">
                  <span>{formatBytes(item.size_bytes)}</span>
                  <span className="text-slate-mid">•</span>
                  <span>{getKindLabel(item.kind)}</span>
                </div>
                <div className="flex items-center gap-2 mt-2 text-xs">
                  {item.on_local && (
                    <span
                      className={clsx(
                        'flex items-center gap-1 px-2 py-0.5 rounded-full',
                        target === 'local' || target === 'both'
                          ? 'bg-red-500/20 text-red-400'
                          : 'bg-green-500/20 text-green-400'
                      )}
                    >
                      <HardDrive className="w-3 h-3" />
                      Local {(target === 'local' || target === 'both') && '(will delete)'}
                    </span>
                  )}
                  {item.on_backup && (
                    <span
                      className={clsx(
                        'flex items-center gap-1 px-2 py-0.5 rounded-full',
                        target === 'backup' || target === 'both'
                          ? 'bg-red-500/20 text-red-400'
                          : 'bg-green-500/20 text-green-400'
                      )}
                    >
                      <Cloud className="w-3 h-3" />
                      Backup {(target === 'backup' || target === 'both') && '(will delete)'}
                    </span>
                  )}
                </div>
              </div>
            </div>
          </div>

          {/* Warning: Last copy */}
          {isLastCopy && (
            <div className="flex items-start gap-3 p-4 bg-red-500/10 border border-red-500/20 rounded-xl">
              <AlertTriangle className="w-5 h-5 text-red-500 flex-shrink-0 mt-0.5" />
              <div>
                <div className="font-medium text-red-400">
                  This is the ONLY copy of this model!
                </div>
                <div className="text-sm text-red-400/80 mt-1">
                  Deleting it will permanently remove it.
                  {item.origin?.provider && (
                    <> You&apos;ll need to re-download from {item.origin.provider}.</>
                  )}
                </div>
              </div>
            </div>
          )}

          {/* Warning: Referenced by packs */}
          {isReferenced && (
            <div className="flex items-start gap-3 p-4 bg-amber-500/10 border border-amber-500/20 rounded-xl">
              <Info className="w-5 h-5 text-amber-500 flex-shrink-0 mt-0.5" />
              <div>
                <div className="font-medium text-amber-400">
                  This blob is used by {item.used_by_packs.length} pack(s)
                </div>
                <div className="text-sm text-amber-400/80 mt-1">
                  {item.used_by_packs.slice(0, 3).join(', ')}
                  {item.used_by_packs.length > 3 && ` and ${item.used_by_packs.length - 3} more`}
                </div>
                {item.active_in_uis.length > 0 && (
                  <div className="text-sm text-amber-400/80 mt-1">
                    Active in: {item.active_in_uis.join(', ')}
                  </div>
                )}
              </div>
            </div>
          )}

          {/* Safe delete message */}
          {!isLastCopy && (
            <div className="flex items-start gap-3 p-4 bg-green-500/10 border border-green-500/20 rounded-xl">
              <Shield className="w-5 h-5 text-green-500 flex-shrink-0 mt-0.5" />
              <div className="text-sm text-green-400">
                {target === 'local' && item.on_backup && (
                  <>Backup copy will be preserved. You can restore later.</>
                )}
                {target === 'backup' && item.on_local && (
                  <>Local copy will be preserved.</>
                )}
              </div>
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="flex items-center justify-end gap-3 p-6 border-t border-slate-mid/30">
          <Button
            variant="secondary"
            onClick={() => onOpenChange(false)}
            disabled={isLoading}
          >
            Cancel
          </Button>
          <Button
            variant={isLastCopy ? 'danger' : 'primary'}
            onClick={onConfirm}
            isLoading={isLoading}
            leftIcon={isLastCopy ? <AlertTriangle className="w-4 h-4" /> : <Trash2 className="w-4 h-4" />}
          >
            {isLastCopy ? 'Delete Permanently' : 'Delete'}
          </Button>
        </div>
      </div>
    </div>
  )

  return createPortal(dialogContent, document.body)
}
