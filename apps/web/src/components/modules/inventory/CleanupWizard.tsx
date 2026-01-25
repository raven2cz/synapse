/**
 * CleanupWizard - 3-Step Wizard for Orphan Cleanup
 *
 * A safe, guided cleanup process for orphan blobs.
 * Steps:
 * 1. Scan - Dry run to find orphans
 * 2. Review - Show what will be deleted, allow user to confirm
 * 3. Complete - Show results and space freed
 */
import { useState, useEffect } from 'react'
import { createPortal } from 'react-dom'
import { clsx } from 'clsx'
import {
  X,
  Trash2,
  Search,
  CheckCircle,
  Loader2,
  AlertTriangle,
  HardDrive,
} from 'lucide-react'
import { Button } from '../../ui/Button'
import { Card } from '../../ui/Card'
import { ProgressBar } from '../../ui/ProgressBar'
import { AssetKindIcon, getKindLabel } from './AssetKindIcon'
import { formatBytes } from './utils'
import type { CleanupResult, InventoryItem } from './types'

interface CleanupWizardProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  onScan: () => Promise<CleanupResult>
  onExecute: () => Promise<CleanupResult>
  onComplete: () => void
}

type WizardStep = 'scan' | 'review' | 'executing' | 'complete'

export function CleanupWizard({
  open,
  onOpenChange,
  onScan,
  onExecute,
  onComplete,
}: CleanupWizardProps) {
  const [step, setStep] = useState<WizardStep>('scan')
  const [isLoading, setIsLoading] = useState(false)
  const [scanResult, setScanResult] = useState<CleanupResult | null>(null)
  const [executeResult, setExecuteResult] = useState<CleanupResult | null>(null)
  const [error, setError] = useState<string | null>(null)

  // Reset state when dialog opens
  useEffect(() => {
    if (open) {
      setStep('scan')
      setScanResult(null)
      setExecuteResult(null)
      setError(null)
      setIsLoading(false)
    }
  }, [open])

  // Handle escape key
  useEffect(() => {
    if (!open) return

    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape' && !isLoading && step !== 'executing') {
        onOpenChange(false)
      }
    }

    window.addEventListener('keydown', handleKeyDown)
    return () => window.removeEventListener('keydown', handleKeyDown)
  }, [open, isLoading, step, onOpenChange])

  const handleScan = async () => {
    setIsLoading(true)
    setError(null)
    try {
      const result = await onScan()
      setScanResult(result)
      setStep('review')
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to scan for orphans')
    } finally {
      setIsLoading(false)
    }
  }

  const handleExecute = async () => {
    setStep('executing')
    setIsLoading(true)
    setError(null)
    try {
      const result = await onExecute()
      setExecuteResult(result)
      setStep('complete')
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to cleanup orphans')
      setStep('review')
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
        onClick={!isLoading && step !== 'executing' ? handleClose : undefined}
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
            <div className="p-2 bg-amber-500/20 rounded-xl">
              <Trash2 className="w-6 h-6 text-amber-500" />
            </div>
            <div>
              <h2 className="text-xl font-bold text-text-primary">
                Cleanup Orphan Blobs
              </h2>
              <p className="text-sm text-text-muted">
                Remove unreferenced models to free disk space
              </p>
            </div>
          </div>

          <button
            onClick={handleClose}
            disabled={isLoading || step === 'executing'}
            className={clsx(
              'p-2 rounded-xl transition-colors',
              'hover:bg-white/10',
              (isLoading || step === 'executing') && 'opacity-50 cursor-not-allowed'
            )}
          >
            <X className="w-6 h-6 text-text-muted" />
          </button>
        </div>

        {/* Step Indicator */}
        <div className="flex items-center justify-center gap-4 px-6 py-4 border-b border-slate-mid/30">
          <StepIndicator
            step={1}
            label="Scan"
            current={step === 'scan'}
            completed={step !== 'scan'}
          />
          <div className="w-12 h-0.5 bg-slate-mid/50" />
          <StepIndicator
            step={2}
            label="Review"
            current={step === 'review' || step === 'executing'}
            completed={step === 'complete'}
          />
          <div className="w-12 h-0.5 bg-slate-mid/50" />
          <StepIndicator
            step={3}
            label="Complete"
            current={step === 'complete'}
            completed={false}
          />
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

          {/* Step 1: Scan */}
          {step === 'scan' && (
            <div className="text-center py-8">
              <div className="w-16 h-16 mx-auto mb-6 rounded-2xl bg-slate-mid/30 flex items-center justify-center">
                <Search className="w-8 h-8 text-text-muted" />
              </div>
              <h3 className="text-lg font-medium text-text-primary mb-2">
                Scan for Orphan Blobs
              </h3>
              <p className="text-text-muted mb-6 max-w-sm mx-auto">
                This will scan your storage for blobs that are not referenced by any pack.
                They can be safely deleted to free disk space.
              </p>
              <Button
                variant="primary"
                size="lg"
                onClick={handleScan}
                isLoading={isLoading}
                leftIcon={<Search className="w-4 h-4" />}
              >
                {isLoading ? 'Scanning...' : 'Start Scan'}
              </Button>
            </div>
          )}

          {/* Step 2: Review */}
          {step === 'review' && scanResult && (
            <div className="space-y-6">
              {scanResult.orphans_found === 0 ? (
                <div className="text-center py-8">
                  <div className="w-16 h-16 mx-auto mb-6 rounded-2xl bg-green-500/20 flex items-center justify-center">
                    <CheckCircle className="w-8 h-8 text-green-500" />
                  </div>
                  <h3 className="text-lg font-medium text-text-primary mb-2">
                    No Orphans Found
                  </h3>
                  <p className="text-text-muted">
                    Your storage is clean! All blobs are referenced by packs.
                  </p>
                </div>
              ) : (
                <>
                  {/* Summary cards */}
                  <div className="grid grid-cols-2 gap-4">
                    <Card padding="md" className="text-center">
                      <div className="text-3xl font-bold text-text-primary">
                        {scanResult.orphans_found}
                      </div>
                      <div className="text-sm text-text-muted mt-1">
                        Orphan blobs found
                      </div>
                    </Card>
                    <Card padding="md" className="text-center">
                      <div className="text-3xl font-bold text-amber-500">
                        {formatBytes(scanResult.bytes_freed)}
                      </div>
                      <div className="text-sm text-text-muted mt-1">
                        Will be freed
                      </div>
                    </Card>
                  </div>

                  {/* Items list */}
                  <div>
                    <h4 className="text-sm font-medium text-text-secondary mb-3">
                      Items to delete ({scanResult.deleted.length})
                    </h4>
                    <div className="max-h-64 overflow-y-auto border border-slate-mid/30 rounded-xl">
                      {scanResult.deleted.map((item) => (
                        <OrphanItemRow key={item.sha256} item={item} />
                      ))}
                    </div>
                  </div>
                </>
              )}
            </div>
          )}

          {/* Step 2.5: Executing */}
          {step === 'executing' && (
            <div className="text-center py-8">
              <div className="w-16 h-16 mx-auto mb-6 rounded-2xl bg-amber-500/20 flex items-center justify-center">
                <Loader2 className="w-8 h-8 text-amber-500 animate-spin" />
              </div>
              <h3 className="text-lg font-medium text-text-primary mb-2">
                Cleaning Up...
              </h3>
              <p className="text-text-muted mb-4">
                Deleting {scanResult?.orphans_found} orphan blobs
              </p>
              <div className="max-w-xs mx-auto">
                <ProgressBar progress={50} size="md" />
              </div>
            </div>
          )}

          {/* Step 3: Complete */}
          {step === 'complete' && executeResult && (
            <div className="text-center py-8">
              <div className="w-16 h-16 mx-auto mb-6 rounded-2xl bg-green-500/20 flex items-center justify-center">
                <CheckCircle className="w-8 h-8 text-green-500" />
              </div>
              <h3 className="text-xl font-bold text-text-primary mb-2">
                Cleanup Complete!
              </h3>
              <p className="text-text-muted mb-6">
                Successfully deleted {executeResult.orphans_deleted} orphan blobs
              </p>

              <div className="inline-flex items-center gap-3 px-6 py-3 bg-green-500/10 border border-green-500/20 rounded-xl">
                <HardDrive className="w-5 h-5 text-green-500" />
                <span className="text-lg font-medium text-green-400">
                  {formatBytes(executeResult.bytes_freed)} freed
                </span>
              </div>

              {executeResult.errors.length > 0 && (
                <div className="mt-6 text-left max-w-md mx-auto">
                  <h4 className="text-sm font-medium text-amber-400 mb-2">
                    Some errors occurred:
                  </h4>
                  <ul className="text-sm text-text-muted space-y-1">
                    {executeResult.errors.map((err, i) => (
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
          {step === 'scan' && (
            <Button variant="secondary" onClick={handleClose}>
              Cancel
            </Button>
          )}

          {step === 'review' && scanResult && (
            <>
              <Button variant="secondary" onClick={handleClose}>
                Cancel
              </Button>
              {scanResult.orphans_found > 0 && (
                <Button
                  variant="danger"
                  onClick={handleExecute}
                  leftIcon={<Trash2 className="w-4 h-4" />}
                >
                  Delete {scanResult.orphans_found} Orphans
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

// Step indicator component
function StepIndicator({
  step,
  label,
  current,
  completed,
}: {
  step: number
  label: string
  current: boolean
  completed: boolean
}) {
  return (
    <div className="flex items-center gap-2">
      <div
        className={clsx(
          'w-8 h-8 rounded-full flex items-center justify-center text-sm font-medium',
          'transition-colors',
          completed
            ? 'bg-green-500 text-white'
            : current
              ? 'bg-synapse text-white'
              : 'bg-slate-mid/50 text-text-muted'
        )}
      >
        {completed ? (
          <CheckCircle className="w-4 h-4" />
        ) : (
          step
        )}
      </div>
      <span
        className={clsx(
          'text-sm',
          current || completed ? 'text-text-primary' : 'text-text-muted'
        )}
      >
        {label}
      </span>
    </div>
  )
}

// Orphan item row component
function OrphanItemRow({ item }: { item: InventoryItem }) {
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
