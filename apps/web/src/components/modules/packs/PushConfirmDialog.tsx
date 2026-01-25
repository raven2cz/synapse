import { useState, useEffect } from 'react'
import { X, ArrowUp, Trash2, Loader2, AlertTriangle } from 'lucide-react'
import { Button } from '@/components/ui/Button'
import { formatBytes } from '@/lib/utils/format'
import type { PackBlobStatus } from '../inventory/types'

interface PushConfirmDialogProps {
  isOpen: boolean
  onClose: () => void
  onConfirm: (cleanup: boolean) => void
  packName: string
  blobs: PackBlobStatus[]
  isLoading?: boolean
  initialCleanup?: boolean
}

/**
 * Confirmation dialog for pushing (backing up) pack blobs to backup storage.
 * Includes optional cleanup checkbox to delete local copies after backup.
 */
export function PushConfirmDialog({
  isOpen,
  onClose,
  onConfirm,
  packName,
  blobs,
  isLoading = false,
  initialCleanup = false,
}: PushConfirmDialogProps) {
  const [cleanup, setCleanup] = useState(initialCleanup)

  // R1: Sync cleanup state when initialCleanup prop changes
  useEffect(() => {
    setCleanup(initialCleanup)
  }, [initialCleanup])

  if (!isOpen) return null

  // Blobs that need backup (local only)
  const blobsToBackup = blobs.filter(b => b.location === 'local_only')
  // All local blobs (for cleanup calculation)
  const localBlobs = blobs.filter(b => b.on_local)
  const totalBytesToBackup = blobsToBackup.reduce((sum, b) => sum + b.size_bytes, 0)
  const totalBytesToFree = localBlobs.reduce((sum, b) => sum + b.size_bytes, 0)

  // P2: Can confirm if there's something to backup OR cleanup is enabled and there are local blobs
  const canConfirm = blobsToBackup.length > 0 || (cleanup && localBlobs.length > 0)

  const handleConfirm = () => {
    onConfirm(cleanup)
  }

  // Determine what the dialog should show - free only mode when all already backed up
  const isFreeOnly = blobsToBackup.length === 0 && cleanup && localBlobs.length > 0

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
        <div className="bg-gradient-to-r from-amber-500/20 to-orange-500/20 border-b border-amber-500/30 p-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <div className="p-2 bg-amber-500/20 rounded-xl">
                <ArrowUp className="w-6 h-6 text-amber-400" />
              </div>
              <div>
                <h2 className="text-lg font-bold text-text-primary">
                  {isFreeOnly ? 'Free Local Space' : 'Push Pack to Backup'}
                </h2>
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
          {/* Show backup info only if there are blobs to backup */}
          {blobsToBackup.length > 0 ? (
            <>
              <p className="text-text-secondary">
                Backup <span className="font-bold text-amber-400">{blobsToBackup.length}</span> blob{blobsToBackup.length !== 1 ? 's' : ''} to external storage:
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
                <span className="text-text-muted">Total to backup:</span>
                <span className="font-bold text-text-primary">{formatBytes(totalBytesToBackup)}</span>
              </div>
            </>
          ) : (
            <p className="text-text-muted text-sm italic">
              All blobs already backed up. You can free local disk space.
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
                Delete local copies after backup
              </div>
              {cleanup && localBlobs.length > 0 && (
                <p className="text-sm text-red-300 mt-1">
                  This will free <span className="font-bold">{formatBytes(totalBytesToFree)}</span> of local disk space
                </p>
              )}
              {localBlobs.length === 0 && (
                <p className="text-sm text-text-muted mt-1">No local copies to delete</p>
              )}
            </div>
          </label>

          {/* Warning for cleanup */}
          {cleanup && localBlobs.length > 0 && (
            <div className="flex items-start gap-2 p-3 bg-amber-500/10 rounded-xl text-sm">
              <AlertTriangle className="w-4 h-4 text-amber-400 flex-shrink-0 mt-0.5" />
              <span className="text-amber-300">
                You will need to run <code className="bg-slate-dark px-1 rounded">Pull</code> to restore these models before using them.
              </span>
            </div>
          )}
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
            onClick={handleConfirm}
            disabled={isLoading || !canConfirm}
            className={cleanup ? 'bg-red-600 hover:bg-red-500 gap-2' : 'bg-amber-600 hover:bg-amber-500 gap-2'}
          >
            {isLoading ? (
              <>
                <Loader2 className="w-4 h-4 animate-spin" />
                {isFreeOnly ? 'Freeing space...' : cleanup ? 'Backing up & cleaning...' : 'Backing up...'}
              </>
            ) : isFreeOnly ? (
              <>
                <Trash2 className="w-4 h-4" />
                Free Local Space
              </>
            ) : cleanup ? (
              <>
                <ArrowUp className="w-4 h-4" />
                <Trash2 className="w-3 h-3" />
                Backup & Free Space
              </>
            ) : (
              <>
                <ArrowUp className="w-4 h-4" />
                Backup Now
              </>
            )}
          </Button>
        </div>
      </div>
    </div>
  )
}
