/**
 * BackupSyncWizard - Wizard for Backup/Restore Operations
 *
 * Handles bulk sync operations between local and backup storage.
 * Steps:
 * 1. Preview - Dry run to show what will be synced
 * 2. Progress - Show sync progress
 * 3. Complete - Show results
 */
import { useState, useEffect } from 'react'
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
} from 'lucide-react'
import { Button } from '../../ui/Button'
import { Card } from '../../ui/Card'
import { ProgressBar } from '../../ui/ProgressBar'
import { AssetKindIcon, getKindLabel } from './AssetKindIcon'
import { formatBytes } from './utils'
import type { SyncResult, SyncItem } from './types'

interface BackupSyncWizardProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  direction: 'to_backup' | 'from_backup'
  onPreview: () => Promise<SyncResult>
  onExecute: () => Promise<SyncResult>
  onComplete: () => void
}

type WizardStep = 'preview' | 'syncing' | 'complete'

export function BackupSyncWizard({
  open,
  onOpenChange,
  direction,
  onPreview,
  onExecute,
  onComplete,
}: BackupSyncWizardProps) {
  const [step, setStep] = useState<WizardStep>('preview')
  const [isLoading, setIsLoading] = useState(false)
  const [previewResult, setPreviewResult] = useState<SyncResult | null>(null)
  const [syncResult, setSyncResult] = useState<SyncResult | null>(null)
  const [error, setError] = useState<string | null>(null)

  const isToBackup = direction === 'to_backup'

  // Load preview when dialog opens
  useEffect(() => {
    if (open) {
      setStep('preview')
      setPreviewResult(null)
      setSyncResult(null)
      setError(null)
      loadPreview()
    }
  }, [open])

  const loadPreview = async () => {
    setIsLoading(true)
    setError(null)
    try {
      const result = await onPreview()
      setPreviewResult(result)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load preview')
    } finally {
      setIsLoading(false)
    }
  }

  // Handle escape key
  useEffect(() => {
    if (!open) return

    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape' && !isLoading && step !== 'syncing') {
        handleClose()
      }
    }

    window.addEventListener('keydown', handleKeyDown)
    return () => window.removeEventListener('keydown', handleKeyDown)
  }, [open, isLoading, step])

  const handleSync = async () => {
    setStep('syncing')
    setIsLoading(true)
    setError(null)
    try {
      const result = await onExecute()
      setSyncResult(result)
      setStep('complete')
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Sync failed')
      setStep('preview')
    } finally {
      setIsLoading(false)
    }
  }

  const handleClose = () => {
    if (step === 'complete') {
      onComplete()
    }
    onOpenChange(false)
  }

  if (!open) return null

  const dialogContent = (
    <div className="fixed inset-0 z-[100] flex items-center justify-center">
      {/* Backdrop */}
      <div
        className="absolute inset-0 bg-black/80 backdrop-blur-sm"
        onClick={!isLoading && step !== 'syncing' ? handleClose : undefined}
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
            <div className={clsx(
              'p-2 rounded-xl',
              isToBackup ? 'bg-blue-500/20' : 'bg-green-500/20'
            )}>
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
            disabled={isLoading || step === 'syncing'}
            className={clsx(
              'p-2 rounded-xl transition-colors',
              'hover:bg-white/10',
              (isLoading || step === 'syncing') && 'opacity-50 cursor-not-allowed'
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
          {step === 'preview' && isLoading && (
            <div className="flex items-center justify-center py-16">
              <Loader2 className="w-8 h-8 animate-spin text-synapse" />
            </div>
          )}

          {/* Preview: No items to sync */}
          {step === 'preview' && !isLoading && previewResult?.blobs_to_sync === 0 && (
            <div className="text-center py-8">
              <div className="w-16 h-16 mx-auto mb-6 rounded-2xl bg-green-500/20 flex items-center justify-center">
                <CheckCircle className="w-8 h-8 text-green-500" />
              </div>
              <h3 className="text-lg font-medium text-text-primary mb-2">
                Already Synced!
              </h3>
              <p className="text-text-muted">
                {isToBackup
                  ? 'All local blobs are already backed up.'
                  : 'All backup blobs are already restored locally.'}
              </p>
            </div>
          )}

          {/* Preview: Items to sync */}
          {step === 'preview' && !isLoading && previewResult && previewResult.blobs_to_sync > 0 && (
            <div className="space-y-6">
              {/* Summary cards */}
              <div className="grid grid-cols-2 gap-4">
                <Card padding="md" className="text-center">
                  <div className="text-3xl font-bold text-text-primary">
                    {previewResult.blobs_to_sync}
                  </div>
                  <div className="text-sm text-text-muted mt-1">
                    Blobs to {isToBackup ? 'backup' : 'restore'}
                  </div>
                </Card>
                <Card padding="md" className="text-center">
                  <div className="text-3xl font-bold text-synapse">
                    {formatBytes(previewResult.bytes_to_sync)}
                  </div>
                  <div className="text-sm text-text-muted mt-1">
                    Total size
                  </div>
                </Card>
              </div>

              {/* Direction visualization */}
              <div className="flex items-center justify-center gap-4 py-4">
                <div className="flex items-center gap-2">
                  <HardDrive className={clsx(
                    'w-6 h-6',
                    isToBackup ? 'text-synapse' : 'text-text-muted'
                  )} />
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
                  <Cloud className={clsx(
                    'w-6 h-6',
                    isToBackup ? 'text-text-muted' : 'text-synapse'
                  )} />
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
                  <div className="text-sm text-amber-400">
                    {previewResult.space_warning}
                  </div>
                </div>
              )}
            </div>
          )}

          {/* Syncing progress */}
          {step === 'syncing' && (
            <div className="text-center py-8">
              <div className={clsx(
                'w-16 h-16 mx-auto mb-6 rounded-2xl flex items-center justify-center',
                isToBackup ? 'bg-blue-500/20' : 'bg-green-500/20'
              )}>
                <Loader2 className={clsx(
                  'w-8 h-8 animate-spin',
                  isToBackup ? 'text-blue-500' : 'text-green-500'
                )} />
              </div>
              <h3 className="text-lg font-medium text-text-primary mb-2">
                {isToBackup ? 'Backing up...' : 'Restoring...'}
              </h3>
              <p className="text-text-muted mb-4">
                {syncResult?.blobs_synced || 0} / {previewResult?.blobs_to_sync || 0} blobs
              </p>
              <div className="max-w-xs mx-auto">
                <ProgressBar
                  progress={
                    ((syncResult?.blobs_synced || 0) /
                      (previewResult?.blobs_to_sync || 1)) * 100
                  }
                  size="md"
                />
              </div>
            </div>
          )}

          {/* Complete */}
          {step === 'complete' && syncResult && (
            <div className="text-center py-8">
              <div className="w-16 h-16 mx-auto mb-6 rounded-2xl bg-green-500/20 flex items-center justify-center">
                <CheckCircle className="w-8 h-8 text-green-500" />
              </div>
              <h3 className="text-xl font-bold text-text-primary mb-2">
                {isToBackup ? 'Backup Complete!' : 'Restore Complete!'}
              </h3>
              <p className="text-text-muted mb-6">
                Successfully synced {syncResult.blobs_synced} blobs
              </p>

              <div className="inline-flex items-center gap-3 px-6 py-3 bg-green-500/10 border border-green-500/20 rounded-xl">
                {isToBackup ? (
                  <Cloud className="w-5 h-5 text-green-500" />
                ) : (
                  <HardDrive className="w-5 h-5 text-green-500" />
                )}
                <span className="text-lg font-medium text-green-400">
                  {formatBytes(syncResult.bytes_synced)} transferred
                </span>
              </div>

              {syncResult.errors && syncResult.errors.length > 0 && (
                <div className="mt-6 text-left max-w-md mx-auto">
                  <h4 className="text-sm font-medium text-amber-400 mb-2">
                    Some errors occurred:
                  </h4>
                  <ul className="text-sm text-text-muted space-y-1">
                    {syncResult.errors.map((err, i) => (
                      <li key={i} className="truncate">• {err}</li>
                    ))}
                  </ul>
                </div>
              )}
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="flex items-center justify-end gap-3 p-6 border-t border-slate-mid/30">
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

          {step === 'complete' && (
            <Button variant="primary" onClick={handleClose}>
              Close
            </Button>
          )}
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
          <div className="font-medium text-text-primary truncate">
            {item.display_name}
          </div>
          <div className="text-xs text-text-muted">
            {getKindLabel(item.kind)}
          </div>
        </div>
      </div>
      <div className="font-mono text-sm text-text-secondary">
        {formatBytes(item.size_bytes)}
      </div>
    </div>
  )
}
