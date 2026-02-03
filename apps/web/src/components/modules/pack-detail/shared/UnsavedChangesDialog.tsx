/**
 * UnsavedChangesDialog
 *
 * Modal dialog warning users about unsaved changes when they try to:
 * - Navigate away from the page
 * - Close the edit mode
 * - Close the browser tab
 *
 * Uses browser beforeunload event for tab close protection.
 */

import { useEffect } from 'react'
import { AlertTriangle, Save, Trash2, X } from 'lucide-react'
import { clsx } from 'clsx'
import { Button } from '@/components/ui/Button'
import { ANIMATION_PRESETS } from '../constants'

// =============================================================================
// Types
// =============================================================================

export interface UnsavedChangesDialogProps {
  /**
   * Whether the dialog is open
   */
  isOpen: boolean

  /**
   * Callback when user chooses to save
   */
  onSave: () => void

  /**
   * Callback when user chooses to discard
   */
  onDiscard: () => void

  /**
   * Callback when user cancels (stays on page)
   */
  onCancel: () => void

  /**
   * Whether save operation is in progress
   */
  isSaving?: boolean

  /**
   * Custom message to display
   */
  message?: string
}

// =============================================================================
// Browser Beforeunload Hook
// =============================================================================

/**
 * Hook to warn user when closing browser tab with unsaved changes
 */
export function useBeforeUnload(hasUnsavedChanges: boolean) {
  useEffect(() => {
    if (!hasUnsavedChanges) return

    const handleBeforeUnload = (e: BeforeUnloadEvent) => {
      e.preventDefault()
      // Chrome requires returnValue to be set
      e.returnValue = 'You have unsaved changes. Are you sure you want to leave?'
      return e.returnValue
    }

    window.addEventListener('beforeunload', handleBeforeUnload)
    return () => window.removeEventListener('beforeunload', handleBeforeUnload)
  }, [hasUnsavedChanges])
}

// =============================================================================
// Component
// =============================================================================

export function UnsavedChangesDialog({
  isOpen,
  onSave,
  onDiscard,
  onCancel,
  isSaving = false,
  message = 'You have unsaved changes that will be lost if you leave.',
}: UnsavedChangesDialogProps) {
  // Handle escape key
  useEffect(() => {
    if (!isOpen) return

    const handleEscape = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        onCancel()
      }
    }

    window.addEventListener('keydown', handleEscape)
    return () => window.removeEventListener('keydown', handleEscape)
  }, [isOpen, onCancel])

  if (!isOpen) return null

  return (
    <div
      className={clsx(
        "fixed inset-0 bg-black/70 z-50",
        "flex items-center justify-center p-4",
        ANIMATION_PRESETS.fadeIn
      )}
      onClick={(e) => {
        if (e.target === e.currentTarget) onCancel()
      }}
    >
      <div
        className={clsx(
          "bg-slate-deep rounded-2xl p-6 max-w-md w-full",
          "border border-slate-mid/50",
          "shadow-2xl",
          ANIMATION_PRESETS.scaleIn
        )}
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header with Warning Icon */}
        <div className="flex items-center gap-3 mb-4">
          <div className={clsx(
            "p-2 rounded-full",
            "bg-amber-500/20"
          )}>
            <AlertTriangle className="w-6 h-6 text-amber-400" />
          </div>
          <div>
            <h3 className="text-lg font-semibold text-text-primary">
              Unsaved Changes
            </h3>
            <p className="text-sm text-text-muted">
              What would you like to do?
            </p>
          </div>

          {/* Close button */}
          <button
            onClick={onCancel}
            className={clsx(
              "ml-auto p-2 rounded-lg",
              "hover:bg-slate-mid transition-colors duration-200"
            )}
          >
            <X className="w-5 h-5 text-text-muted" />
          </button>
        </div>

        {/* Message */}
        <p className="text-text-secondary mb-6">
          {message}
        </p>

        {/* Action Buttons */}
        <div className="flex gap-3">
          {/* Save Button - Primary */}
          <Button
            variant="primary"
            onClick={onSave}
            disabled={isSaving}
            className="flex-1"
          >
            <Save className="w-4 h-4" />
            {isSaving ? 'Saving...' : 'Save Changes'}
          </Button>

          {/* Discard Button - Destructive */}
          <Button
            variant="secondary"
            onClick={onDiscard}
            disabled={isSaving}
            className={clsx(
              "flex-1 text-red-400",
              "hover:bg-red-500/20 hover:text-red-300"
            )}
          >
            <Trash2 className="w-4 h-4" />
            Discard
          </Button>
        </div>

        {/* Cancel hint */}
        <p className="text-center text-xs text-text-muted mt-4">
          Press <kbd className="px-1.5 py-0.5 rounded bg-slate-mid text-text-secondary">Esc</kbd> to cancel
        </p>
      </div>
    </div>
  )
}

export default UnsavedChangesDialog
