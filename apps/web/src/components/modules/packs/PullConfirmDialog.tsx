import { X, ArrowDown, Info, Loader2 } from 'lucide-react'
import { Button } from '@/components/ui/Button'
import { formatBytes } from '@/lib/utils/format'
import type { PackBlobStatus } from '../inventory/types'

interface PullConfirmDialogProps {
  isOpen: boolean
  onClose: () => void
  onConfirm: () => void
  packName: string
  blobs: PackBlobStatus[]
  isLoading?: boolean
}

/**
 * Confirmation dialog for pulling (restoring) pack blobs from backup.
 */
export function PullConfirmDialog({
  isOpen,
  onClose,
  onConfirm,
  packName,
  blobs,
  isLoading = false,
}: PullConfirmDialogProps) {
  if (!isOpen) return null

  // Filter to backup-only blobs
  const blobsToRestore = blobs.filter(b => b.location === 'backup_only')
  const totalBytes = blobsToRestore.reduce((sum, b) => sum + b.size_bytes, 0)

  return (
    <div
      className="fixed inset-0 bg-black/80 backdrop-blur-sm flex items-center justify-center z-50 p-4"
      onClick={onClose}
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
                <h2 className="text-lg font-bold text-text-primary">Pull Pack from Backup</h2>
                <p className="text-sm text-text-muted">{packName}</p>
              </div>
            </div>
            <button
              onClick={onClose}
              disabled={isLoading}
              className="p-2 hover:bg-slate-mid rounded-xl text-text-muted hover:text-text-primary transition-colors disabled:opacity-50"
            >
              <X className="w-5 h-5" />
            </button>
          </div>
        </div>

        {/* Content */}
        <div className="p-4 space-y-4">
          <p className="text-text-secondary">
            Restore <span className="font-bold text-blue-400">{blobsToRestore.length}</span> blob{blobsToRestore.length !== 1 ? 's' : ''} from backup:
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
            <span className="text-text-muted">Total:</span>
            <span className="font-bold text-text-primary">{formatBytes(totalBytes)}</span>
          </div>

          {/* Info */}
          <div className="flex items-start gap-2 p-3 bg-blue-500/10 rounded-xl text-sm">
            <Info className="w-4 h-4 text-blue-400 flex-shrink-0 mt-0.5" />
            <span className="text-blue-300">
              Profile stays on global. Models will be available locally without activating work profile.
            </span>
          </div>
        </div>

        {/* Actions */}
        <div className="flex items-center justify-end gap-3 p-4 border-t border-slate-mid">
          <Button
            variant="ghost"
            onClick={onClose}
            disabled={isLoading}
          >
            Cancel
          </Button>
          <Button
            onClick={onConfirm}
            disabled={isLoading || blobsToRestore.length === 0}
            className="bg-blue-600 hover:bg-blue-500 gap-2"
          >
            {isLoading ? (
              <>
                <Loader2 className="w-4 h-4 animate-spin" />
                Restoring...
              </>
            ) : (
              <>
                <ArrowDown className="w-4 h-4" />
                Restore from Backup
              </>
            )}
          </Button>
        </div>
      </div>
    </div>
  )
}
