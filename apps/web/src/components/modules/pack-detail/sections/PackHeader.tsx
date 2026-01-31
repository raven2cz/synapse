/**
 * PackHeader Section
 *
 * Displays pack identity: name, version, badges, and primary actions.
 *
 * FUNKCE ZACHOVÁNY:
 * - Use Pack button (aktivace work profile)
 * - Source link (external)
 * - Delete button
 * - Model type badge
 * - Base model badge
 * - Version display
 *
 * VIZUÁLNĚ VYLEPŠENO:
 * - Premium hover efekty
 * - Animace při načtení
 * - Lepší badge styling
 *
 * PHASE 2 - EDIT MODE:
 * - Edit button toggle
 * - Save/Discard buttons in edit mode
 * - Unsaved changes indicator
 */

import { Loader2, ExternalLink, Trash2, Zap, Sparkles, Pencil, Save, X, AlertCircle } from 'lucide-react'
import { clsx } from 'clsx'
import { Button } from '@/components/ui/Button'
import type { PackDetail } from '../types'
import { ANIMATION_PRESETS } from '../constants'

// =============================================================================
// Types
// =============================================================================

export interface PackHeaderProps {
  /**
   * Pack data to display
   */
  pack: PackDetail

  /**
   * Handler for "Use Pack" action
   */
  onUsePack: () => void

  /**
   * Handler for delete action
   */
  onDelete: () => void

  /**
   * Whether use pack mutation is pending
   */
  isUsingPack?: boolean

  /**
   * Whether delete mutation is pending
   */
  isDeleting?: boolean

  /**
   * Animation delay for staggered entrance
   */
  animationDelay?: number

  // === Edit Mode Props ===

  /**
   * Whether edit mode is active
   */
  isEditing?: boolean

  /**
   * Whether there are unsaved changes
   */
  hasUnsavedChanges?: boolean

  /**
   * Whether save is in progress
   */
  isSaving?: boolean

  /**
   * Handler to start edit mode
   */
  onStartEdit?: () => void

  /**
   * Handler to save changes
   */
  onSaveChanges?: () => void

  /**
   * Handler to discard changes
   */
  onDiscardChanges?: () => void

  // === Plugin Props ===

  /**
   * Additional actions from plugin (rendered after Edit button)
   */
  pluginActions?: React.ReactNode
}

// =============================================================================
// Sub-components
// =============================================================================

interface BadgeProps {
  children: React.ReactNode
  variant?: 'primary' | 'secondary' | 'muted'
  className?: string
}

function Badge({ children, variant = 'muted', className }: BadgeProps) {
  const variantClasses = {
    primary: 'bg-synapse/20 text-synapse border-synapse/30',
    secondary: 'bg-pulse/20 text-pulse border-pulse/30',
    muted: 'bg-slate-mid/50 text-text-secondary border-slate-mid',
  }

  return (
    <span
      className={clsx(
        'px-3 py-1 rounded-lg text-sm font-medium border',
        'transition-all duration-200',
        'hover:scale-105 hover:shadow-sm',
        variantClasses[variant],
        className
      )}
    >
      {children}
    </span>
  )
}

// =============================================================================
// Component
// =============================================================================

export function PackHeader({
  pack,
  onUsePack,
  onDelete,
  isUsingPack = false,
  isDeleting = false,
  animationDelay = 0,
  // Edit mode props
  isEditing = false,
  hasUnsavedChanges = false,
  isSaving = false,
  onStartEdit,
  onSaveChanges,
  onDiscardChanges,
  // Plugin props
  pluginActions,
}: PackHeaderProps) {
  return (
    <div
      className={clsx(
        'flex items-start justify-between gap-6',
        ANIMATION_PRESETS.fadeIn
      )}
      style={{ animationDelay: `${animationDelay}ms`, animationFillMode: 'both' }}
    >
      {/* Left: Pack Identity */}
      <div className="flex-1 min-w-0">
        {/* Pack Name with subtle animation */}
        <div className="flex items-center gap-3">
          <h1 className={clsx(
            'text-2xl font-bold text-text-primary truncate',
            'transition-colors duration-200',
            'hover:text-synapse'
          )}>
            {pack.name}
          </h1>

          {/* Edit Mode Indicator */}
          {isEditing && (
            <span className={clsx(
              'px-2 py-0.5 rounded text-xs font-medium',
              'bg-synapse/20 text-synapse border border-synapse/30',
              'animate-pulse'
            )}>
              Editing
            </span>
          )}

          {/* Unsaved Changes Warning */}
          {hasUnsavedChanges && !isEditing && (
            <span className={clsx(
              'flex items-center gap-1 px-2 py-0.5 rounded text-xs font-medium',
              'bg-amber-500/20 text-amber-400 border border-amber-500/30'
            )}>
              <AlertCircle className="w-3 h-3" />
              Unsaved
            </span>
          )}
        </div>

        {/* Badges Row */}
        <div className="flex items-center gap-3 mt-3 flex-wrap">
          {/* Model Type Badge (LoRA, Checkpoint, etc.) */}
          {pack.model_info?.model_type && (
            <Badge variant="primary">
              <span className="flex items-center gap-1.5">
                <Sparkles className="w-3.5 h-3.5" />
                {pack.model_info.model_type}
              </span>
            </Badge>
          )}

          {/* Base Model Badge */}
          {pack.model_info?.base_model && (
            <Badge variant="secondary">
              {pack.model_info.base_model}
            </Badge>
          )}

          {/* Version */}
          <Badge variant="muted">
            v{pack.version}
          </Badge>
        </div>
      </div>

      {/* Right: Action Buttons */}
      <div className="flex gap-2 flex-shrink-0">
        {isEditing ? (
          // Edit Mode Actions
          <>
            {/* Save Button */}
            <Button
              variant="primary"
              onClick={onSaveChanges}
              disabled={isSaving || !hasUnsavedChanges}
              className={clsx(
                'transition-all duration-200',
                !isSaving && hasUnsavedChanges && 'hover:shadow-lg hover:shadow-synapse/20 hover:scale-105'
              )}
            >
              {isSaving ? (
                <Loader2 className="w-4 h-4 animate-spin" />
              ) : (
                <Save className="w-4 h-4" />
              )}
              Save
            </Button>

            {/* Discard Button */}
            <Button
              variant="secondary"
              onClick={onDiscardChanges}
              disabled={isSaving}
              className={clsx(
                'transition-all duration-200',
                !isSaving && 'hover:scale-105'
              )}
            >
              <X className="w-4 h-4" />
              Discard
            </Button>
          </>
        ) : (
          // Normal Mode Actions
          <>
            {/* Edit Button */}
            {onStartEdit && (
              <Button
                variant="secondary"
                onClick={onStartEdit}
                className="transition-all duration-200 hover:scale-105 hover:bg-synapse/20 hover:text-synapse"
              >
                <Pencil className="w-4 h-4" />
                Edit
              </Button>
            )}

            {/* Plugin Actions (e.g., Check Updates for Civitai, Console for Install) */}
            {pluginActions}

            {/* Use Pack - Primary CTA */}
            <Button
              variant="primary"
              onClick={onUsePack}
              disabled={isUsingPack}
              className={clsx(
                'transition-all duration-200',
                !isUsingPack && 'hover:shadow-lg hover:shadow-synapse/20 hover:scale-105'
              )}
            >
              {isUsingPack ? (
                <Loader2 className="w-4 h-4 animate-spin" />
              ) : (
                <Zap className="w-4 h-4" />
              )}
              Use
            </Button>

            {/* Source Link */}
            {pack.source_url && (
              <Button
                variant="secondary"
                onClick={() => window.open(pack.source_url, '_blank')}
                className="transition-all duration-200 hover:scale-105"
              >
                <ExternalLink className="w-4 h-4" />
                Source
              </Button>
            )}

            {/* Delete Button */}
            <Button
              variant="secondary"
              onClick={onDelete}
              disabled={isDeleting}
              className={clsx(
                'text-red-400 transition-all duration-200',
                !isDeleting && 'hover:bg-red-500/20 hover:scale-105 hover:text-red-300'
              )}
            >
              {isDeleting ? (
                <Loader2 className="w-4 h-4 animate-spin" />
              ) : (
                <Trash2 className="w-4 h-4" />
              )}
            </Button>
          </>
        )}
      </div>
    </div>
  )
}

export default PackHeader
