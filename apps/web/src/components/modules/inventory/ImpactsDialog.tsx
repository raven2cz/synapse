/**
 * ImpactsDialog - Show Blob Impact Analysis
 *
 * Displays what packs and UIs would be affected if a blob is deleted.
 * Used to help users understand dependencies before making changes.
 */
import { useEffect } from 'react'
import { createPortal } from 'react-dom'
import { clsx } from 'clsx'
import {
  X,
  Info,
  Package,
  Monitor,
  AlertTriangle,
  CheckCircle,
  Loader2,
} from 'lucide-react'
import { Button } from '../../ui/Button'
import { Card } from '../../ui/Card'
import { AssetKindIcon } from './AssetKindIcon'
import { StatusBadge } from './StatusBadge'
import { formatBytes } from './utils'
import type { ImpactAnalysis } from './types'

interface ImpactsDialogProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  analysis: ImpactAnalysis | null
  isLoading?: boolean
  error?: string | null
}

export function ImpactsDialog({
  open,
  onOpenChange,
  analysis,
  isLoading = false,
  error = null,
}: ImpactsDialogProps) {
  // Handle escape key
  useEffect(() => {
    if (!open) return

    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        onOpenChange(false)
      }
    }

    window.addEventListener('keydown', handleKeyDown)
    return () => window.removeEventListener('keydown', handleKeyDown)
  }, [open, onOpenChange])

  if (!open) return null

  const dialogContent = (
    <div className="fixed inset-0 z-[100] flex items-center justify-center">
      {/* Backdrop */}
      <div
        className="absolute inset-0 bg-black/80 backdrop-blur-sm"
        onClick={() => onOpenChange(false)}
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
        <div className="flex items-center justify-between p-6 border-b border-slate-mid/30">
          <div className="flex items-center gap-3">
            <div className="p-2 bg-blue-500/20 rounded-xl">
              <Info className="w-6 h-6 text-blue-500" />
            </div>
            <div>
              <h2 className="text-xl font-bold text-text-primary">
                Impact Analysis
              </h2>
              <p className="text-sm text-text-muted">
                What would be affected by removing this blob
              </p>
            </div>
          </div>

          <button
            onClick={() => onOpenChange(false)}
            className="p-2 rounded-xl transition-colors hover:bg-white/10"
          >
            <X className="w-6 h-6 text-text-muted" />
          </button>
        </div>

        {/* Content */}
        <div className="p-6 space-y-4">
          {/* Loading state */}
          {isLoading && (
            <div className="flex items-center justify-center py-8">
              <Loader2 className="w-8 h-8 animate-spin text-synapse" />
            </div>
          )}

          {/* Error state */}
          {error && (
            <div className="flex items-start gap-3 p-4 bg-red-500/10 border border-red-500/20 rounded-xl">
              <AlertTriangle className="w-5 h-5 text-red-500 flex-shrink-0 mt-0.5" />
              <div className="text-sm text-red-400">{error}</div>
            </div>
          )}

          {/* Analysis content */}
          {!isLoading && !error && analysis && (
            <>
              {/* Blob summary */}
              <Card padding="md">
                <div className="flex items-start gap-3">
                  <AssetKindIcon kind={analysis.kind || 'unknown'} size="lg" />
                  <div className="flex-1 min-w-0">
                    <div className="font-medium text-text-primary truncate">
                      {analysis.display_name || analysis.sha256.slice(0, 16) + '...'}
                    </div>
                    <div className="flex items-center gap-2 mt-1">
                      <div className="font-mono text-xs text-text-muted truncate">
                        {analysis.sha256.slice(0, 12)}...
                      </div>
                      <StatusBadge status={analysis.status} size="sm" />
                    </div>
                    <div className="text-sm text-text-muted mt-1">
                      {formatBytes(analysis.size_bytes)}
                    </div>
                  </div>
                </div>
              </Card>

              {/* Safety assessment */}
              <div
                className={clsx(
                  'flex items-start gap-3 p-4 rounded-xl',
                  analysis.can_delete_safely
                    ? 'bg-green-500/10 border border-green-500/20'
                    : 'bg-amber-500/10 border border-amber-500/20'
                )}
              >
                {analysis.can_delete_safely ? (
                  <CheckCircle className="w-5 h-5 text-green-500 flex-shrink-0 mt-0.5" />
                ) : (
                  <AlertTriangle className="w-5 h-5 text-amber-500 flex-shrink-0 mt-0.5" />
                )}
                <div>
                  <div
                    className={clsx(
                      'font-medium',
                      analysis.can_delete_safely ? 'text-green-400' : 'text-amber-400'
                    )}
                  >
                    {analysis.can_delete_safely ? 'Safe to delete' : 'Deletion may cause issues'}
                  </div>
                  {analysis.warning && (
                    <div
                      className={clsx(
                        'text-sm mt-1',
                        analysis.can_delete_safely ? 'text-green-400/80' : 'text-amber-400/80'
                      )}
                    >
                      {analysis.warning}
                    </div>
                  )}
                </div>
              </div>

              {/* Used by packs */}
              {analysis.used_by_packs.length > 0 && (
                <div>
                  <h4 className="flex items-center gap-2 text-sm font-medium text-text-secondary mb-3">
                    <Package className="w-4 h-4" />
                    Used by {analysis.used_by_packs.length} pack(s)
                  </h4>
                  <div className="border border-slate-mid/30 rounded-xl divide-y divide-slate-mid/20">
                    {analysis.used_by_packs.map((pack) => (
                      <div
                        key={pack}
                        className="flex items-center gap-3 px-4 py-3 hover:bg-slate-deep/50"
                      >
                        <Package className="w-4 h-4 text-synapse" />
                        <span className="text-text-primary">{pack}</span>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* Active in UIs */}
              {analysis.active_in_uis.length > 0 && (
                <div>
                  <h4 className="flex items-center gap-2 text-sm font-medium text-text-secondary mb-3">
                    <Monitor className="w-4 h-4" />
                    Active in {analysis.active_in_uis.length} UI(s)
                  </h4>
                  <div className="border border-slate-mid/30 rounded-xl divide-y divide-slate-mid/20">
                    {analysis.active_in_uis.map((ui) => (
                      <div
                        key={ui}
                        className="flex items-center gap-3 px-4 py-3 hover:bg-slate-deep/50"
                      >
                        <Monitor className="w-4 h-4 text-purple-500" />
                        <span className="text-text-primary">{ui}</span>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* No dependencies */}
              {analysis.used_by_packs.length === 0 && analysis.active_in_uis.length === 0 && (
                <div className="text-center py-4 text-text-muted">
                  <p>This blob has no dependencies.</p>
                </div>
              )}
            </>
          )}
        </div>

        {/* Footer */}
        <div className="flex items-center justify-end gap-3 p-6 border-t border-slate-mid/30">
          <Button variant="secondary" onClick={() => onOpenChange(false)}>
            Close
          </Button>
        </div>
      </div>
    </div>
  )

  return createPortal(dialogContent, document.body)
}
