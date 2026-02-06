/**
 * VerifyProgressDialog - Blob Integrity Verification
 *
 * Shows progress and results of verifying blob integrity via SHA256 checksums.
 */
import { useState, useEffect } from 'react'
import { createPortal } from 'react-dom'
import { useTranslation } from 'react-i18next'
import { clsx } from 'clsx'
import {
  X,
  Shield,
  CheckCircle,
  XCircle,
  Loader2,
  AlertTriangle,
} from 'lucide-react'
import { Button } from '../../ui/Button'
import { Card } from '../../ui/Card'
import { ProgressBar } from '../../ui/ProgressBar'
import { formatBytes } from './utils'

export interface VerifyResult {
  total: number
  verified: number
  failed: number
  bytes_verified: number
  errors: Array<{ sha256: string; error: string }>
}

interface VerifyProgressDialogProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  onStart: () => Promise<VerifyResult>
  onComplete: () => void
}

type DialogState = 'ready' | 'verifying' | 'complete'

export function VerifyProgressDialog({
  open,
  onOpenChange,
  onStart,
  onComplete,
}: VerifyProgressDialogProps) {
  const { t } = useTranslation()
  const [state, setState] = useState<DialogState>('ready')
  const [result, setResult] = useState<VerifyResult | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [progress, setProgress] = useState(0)

  // Reset state when dialog opens
  useEffect(() => {
    if (open) {
      setState('ready')
      setResult(null)
      setError(null)
      setProgress(0)
    }
  }, [open])

  // Handle escape key
  useEffect(() => {
    if (!open) return

    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape' && state !== 'verifying') {
        handleClose()
      }
    }

    window.addEventListener('keydown', handleKeyDown)
    return () => window.removeEventListener('keydown', handleKeyDown)
  }, [open, state])

  const handleStart = async () => {
    setState('verifying')
    setError(null)

    // Simulate progress updates
    const progressInterval = setInterval(() => {
      setProgress((prev) => Math.min(prev + 10, 90))
    }, 500)

    try {
      const verifyResult = await onStart()
      setResult(verifyResult)
      setProgress(100)
      setState('complete')
    } catch (err) {
      setError(err instanceof Error ? err.message : t('inventory.verify.error'))
      setState('ready')
    } finally {
      clearInterval(progressInterval)
    }
  }

  const handleClose = () => {
    if (state === 'complete') {
      onComplete()
    }
    onOpenChange(false)
  }

  if (!open) return null

  const allPassed = result && result.failed === 0

  const dialogContent = (
    <div className="fixed inset-0 z-[100] flex items-center justify-center">
      {/* Backdrop */}
      <div
        className="absolute inset-0 bg-black/80 backdrop-blur-sm"
        onClick={state !== 'verifying' ? handleClose : undefined}
      />

      {/* Dialog */}
      <div
        className={clsx(
          'relative w-full max-w-md m-4',
          'bg-slate-dark/95 backdrop-blur-xl',
          'border border-slate-mid/50 rounded-2xl shadow-2xl',
          'animate-in fade-in zoom-in-95 duration-200'
        )}
      >
        {/* Header */}
        <div className="flex items-center justify-between p-6 border-b border-slate-mid/30">
          <div className="flex items-center gap-3">
            <div className={clsx(
              'p-2 rounded-xl',
              state === 'complete' && allPassed
                ? 'bg-green-500/20'
                : state === 'complete' && !allPassed
                  ? 'bg-red-500/20'
                  : 'bg-blue-500/20'
            )}>
              <Shield className={clsx(
                'w-6 h-6',
                state === 'complete' && allPassed
                  ? 'text-green-500'
                  : state === 'complete' && !allPassed
                    ? 'text-red-500'
                    : 'text-blue-500'
              )} />
            </div>
            <div>
              <h2 className="text-xl font-bold text-text-primary">
                {t('inventory.verify.title')}
              </h2>
              <p className="text-sm text-text-muted">
                {t('inventory.verify.subtitle')}
              </p>
            </div>
          </div>

          <button
            onClick={handleClose}
            disabled={state === 'verifying'}
            className={clsx(
              'p-2 rounded-xl transition-colors',
              'hover:bg-white/10',
              state === 'verifying' && 'opacity-50 cursor-not-allowed'
            )}
          >
            <X className="w-6 h-6 text-text-muted" />
          </button>
        </div>

        {/* Content */}
        <div className="p-6">
          {/* Error message */}
          {error && (
            <div className="flex items-start gap-3 p-4 mb-4 bg-red-500/10 border border-red-500/20 rounded-xl">
              <AlertTriangle className="w-5 h-5 text-red-500 flex-shrink-0 mt-0.5" />
              <div className="text-sm text-red-400">{error}</div>
            </div>
          )}

          {/* Ready state */}
          {state === 'ready' && (
            <div className="text-center py-4">
              <div className="w-16 h-16 mx-auto mb-6 rounded-2xl bg-blue-500/20 flex items-center justify-center">
                <Shield className="w-8 h-8 text-blue-500" />
              </div>
              <h3 className="text-lg font-medium text-text-primary mb-2">
                {t('inventory.verify.readyTitle')}
              </h3>
              <p className="text-text-muted mb-6 max-w-sm mx-auto">
                {t('inventory.verify.readyDescription')}
              </p>
            </div>
          )}

          {/* Verifying state */}
          {state === 'verifying' && (
            <div className="text-center py-4">
              <div className="w-16 h-16 mx-auto mb-6 rounded-2xl bg-blue-500/20 flex items-center justify-center">
                <Loader2 className="w-8 h-8 text-blue-500 animate-spin" />
              </div>
              <h3 className="text-lg font-medium text-text-primary mb-2">
                {t('inventory.verify.verifying')}
              </h3>
              <p className="text-text-muted mb-4">
                {t('inventory.verify.verifyingDescription')}
              </p>
              <div className="max-w-xs mx-auto">
                <ProgressBar progress={progress} size="md" />
              </div>
            </div>
          )}

          {/* Complete state */}
          {state === 'complete' && result && (
            <div className="space-y-4">
              {/* Success/Failure icon */}
              <div className="text-center">
                <div className={clsx(
                  'w-16 h-16 mx-auto mb-4 rounded-2xl flex items-center justify-center',
                  allPassed ? 'bg-green-500/20' : 'bg-red-500/20'
                )}>
                  {allPassed ? (
                    <CheckCircle className="w-8 h-8 text-green-500" />
                  ) : (
                    <XCircle className="w-8 h-8 text-red-500" />
                  )}
                </div>
                <h3 className="text-xl font-bold text-text-primary mb-2">
                  {allPassed ? t('inventory.verify.allVerified') : t('inventory.verify.verificationFailed')}
                </h3>
              </div>

              {/* Stats */}
              <div className="grid grid-cols-2 gap-3">
                <Card padding="sm" className="text-center">
                  <div className="flex items-center justify-center gap-2 text-green-500">
                    <CheckCircle className="w-4 h-4" />
                    <span className="text-xl font-bold">{result.verified}</span>
                  </div>
                  <div className="text-xs text-text-muted mt-1">{t('inventory.verify.verified')}</div>
                </Card>
                <Card padding="sm" className="text-center">
                  <div className={clsx(
                    'flex items-center justify-center gap-2',
                    result.failed > 0 ? 'text-red-500' : 'text-text-muted'
                  )}>
                    <XCircle className="w-4 h-4" />
                    <span className="text-xl font-bold">{result.failed}</span>
                  </div>
                  <div className="text-xs text-text-muted mt-1">{t('inventory.verify.failed')}</div>
                </Card>
              </div>

              <div className="text-center text-sm text-text-muted">
                {t('inventory.verify.sizeVerified', { size: formatBytes(result.bytes_verified) })}
              </div>

              {/* Failed items */}
              {result.errors.length > 0 && (
                <div className="mt-4">
                  <h4 className="text-sm font-medium text-red-400 mb-2">
                    {t('inventory.verify.failedBlobs')}
                  </h4>
                  <div className="max-h-32 overflow-y-auto border border-red-500/20 rounded-xl">
                    {result.errors.map((err, i) => (
                      <div
                        key={i}
                        className="flex items-center justify-between px-3 py-2 border-b border-red-500/10 last:border-b-0"
                      >
                        <span className="font-mono text-xs text-text-muted truncate">
                          {err.sha256.slice(0, 16)}...
                        </span>
                        <span className="text-xs text-red-400 truncate ml-2">
                          {err.error}
                        </span>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="flex items-center justify-end gap-3 p-6 border-t border-slate-mid/30">
          {state === 'ready' && (
            <>
              <Button variant="secondary" onClick={handleClose}>
                {t('common.cancel')}
              </Button>
              <Button
                variant="primary"
                onClick={handleStart}
                leftIcon={<Shield className="w-4 h-4" />}
              >
                {t('inventory.verify.start')}
              </Button>
            </>
          )}

          {state === 'complete' && (
            <Button variant="primary" onClick={handleClose}>
              {t('common.close')}
            </Button>
          )}
        </div>
      </div>
    </div>
  )

  return createPortal(dialogContent, document.body)
}
