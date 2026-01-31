/**
 * EditParametersModal
 *
 * Modal for editing generation parameters.
 *
 * FUNKCE ZACHOVÁNY:
 * - Quick-add buttons for common parameters
 * - Editable parameter rows with remove
 * - Custom parameter input
 * - Type conversion (numbers vs strings)
 * - Save/Cancel with loading state
 *
 * VIZUÁLNĚ VYLEPŠENO:
 * - Premium modal design
 * - Enhanced parameter cards
 * - Better visual hierarchy
 */

import { useState, useEffect } from 'react'
import { X, Loader2 } from 'lucide-react'
import { clsx } from 'clsx'
import { Button } from '@/components/ui/Button'
import { ANIMATION_PRESETS } from '../constants'

// =============================================================================
// Types
// =============================================================================

export interface EditParametersModalProps {
  /**
   * Whether modal is open
   */
  isOpen: boolean

  /**
   * Initial parameters to edit
   */
  initialParameters: Record<string, string>

  /**
   * Handler for save action
   */
  onSave: (parameters: Record<string, unknown>) => void

  /**
   * Handler for close/cancel
   */
  onClose: () => void

  /**
   * Whether save is in progress
   */
  isSaving?: boolean
}

// =============================================================================
// Constants
// =============================================================================

const QUICK_ADD_PARAMS = [
  'clipSkip',
  'cfgScale',
  'steps',
  'sampler',
  'scheduler',
  'strength',
  'width',
  'height',
  'denoise',
  'seed',
]

const DEFAULT_VALUES: Record<string, string> = {
  clipSkip: '2',
  cfgScale: '7',
  steps: '20',
  sampler: 'euler',
  scheduler: 'normal',
  strength: '1.0',
  width: '512',
  height: '512',
  denoise: '1.0',
  seed: '-1',
}

// =============================================================================
// Sub-components
// =============================================================================

interface ParameterRowProps {
  paramKey: string
  value: string
  onChange: (value: string) => void
  onRemove: () => void
}

function ParameterRow({ paramKey, value, onChange, onRemove }: ParameterRowProps) {
  return (
    <div
      className={clsx(
        "flex items-center gap-3",
        "bg-obsidian/50 p-3 rounded-xl",
        "transition-all duration-200",
        "hover:bg-obsidian/70"
      )}
    >
      <span className="text-sm text-synapse font-mono min-w-[120px] font-medium">
        {paramKey}
      </span>
      <input
        type="text"
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className={clsx(
          "flex-1 px-3 py-2 rounded-lg",
          "bg-obsidian border border-slate-mid",
          "text-text-primary text-sm",
          "focus:outline-none focus:border-synapse",
          "transition-colors duration-200"
        )}
      />
      <button
        onClick={onRemove}
        className={clsx(
          "p-1.5 rounded-lg",
          "hover:bg-red-500/20 transition-colors duration-200"
        )}
        title="Remove parameter"
      >
        <X className="w-4 h-4 text-red-400" />
      </button>
    </div>
  )
}

// =============================================================================
// Main Component
// =============================================================================

export function EditParametersModal({
  isOpen,
  initialParameters,
  onSave,
  onClose,
  isSaving = false,
}: EditParametersModalProps) {
  const [parameters, setParameters] = useState<Record<string, string>>(initialParameters)
  const [newKey, setNewKey] = useState('')
  const [newValue, setNewValue] = useState('')

  // Reset parameters when modal opens
  useEffect(() => {
    if (isOpen) {
      setParameters(initialParameters)
      setNewKey('')
      setNewValue('')
    }
  }, [isOpen, initialParameters])

  const handleQuickAdd = (key: string) => {
    setParameters(prev => ({
      ...prev,
      [key]: DEFAULT_VALUES[key] || '',
    }))
  }

  const handleUpdateParam = (key: string, value: string) => {
    setParameters(prev => ({ ...prev, [key]: value }))
  }

  const handleRemoveParam = (key: string) => {
    const newParams = { ...parameters }
    delete newParams[key]
    setParameters(newParams)
  }

  const handleAddCustomParam = () => {
    if (newKey.trim()) {
      setParameters(prev => ({ ...prev, [newKey.trim()]: newValue }))
      setNewKey('')
      setNewValue('')
    }
  }

  const handleSave = () => {
    // Convert parameters to proper types
    const converted: Record<string, unknown> = {}
    for (const [key, value] of Object.entries(parameters)) {
      if (value === '') continue
      // Try to parse as number (except for sampler which is always string)
      const numValue = parseFloat(value)
      if (!isNaN(numValue) && key !== 'sampler' && key !== 'scheduler') {
        converted[key] = numValue
      } else {
        converted[key] = value
      }
    }
    onSave(converted)
  }

  if (!isOpen) return null

  // Which quick-add buttons to show
  const availableQuickAdds = QUICK_ADD_PARAMS.filter(key => !parameters[key])

  return (
    <div
      className={clsx(
        "fixed inset-0 bg-black/80 backdrop-blur-sm z-[80]",
        "flex items-center justify-center p-4",
        ANIMATION_PRESETS.fadeIn
      )}
      onClick={(e) => {
        if (e.target === e.currentTarget) onClose()
      }}
    >
      <div
        className={clsx(
          "bg-slate-dark rounded-2xl p-6 max-w-2xl w-full",
          "border border-slate-mid",
          "max-h-[85vh] overflow-hidden flex flex-col",
          "shadow-2xl",
          ANIMATION_PRESETS.scaleIn
        )}
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-xl font-bold text-text-primary">Edit Generation Parameters</h2>
          <button
            onClick={onClose}
            className={clsx(
              "p-2 rounded-lg",
              "hover:bg-slate-mid transition-colors duration-200"
            )}
          >
            <X className="w-5 h-5 text-text-muted" />
          </button>
        </div>

        {/* Quick Add Suggestions */}
        {availableQuickAdds.length > 0 && (
          <div className="mb-4">
            <p className="text-xs text-text-muted mb-2">Quick add:</p>
            <div className="flex flex-wrap gap-2">
              {availableQuickAdds.map(key => (
                <button
                  key={key}
                  onClick={() => handleQuickAdd(key)}
                  className={clsx(
                    "px-3 py-1.5 text-xs rounded-lg font-medium",
                    "bg-synapse/20 hover:bg-synapse/30 text-synapse",
                    "transition-all duration-200 hover:scale-105"
                  )}
                >
                  + {key}
                </button>
              ))}
            </div>
          </div>
        )}

        {/* Parameters List */}
        <div className="flex-1 overflow-y-auto space-y-2 mb-4 min-h-[150px]">
          {Object.entries(parameters).length === 0 ? (
            <p className="text-sm text-text-muted text-center py-8">
              No parameters set. Click quick add buttons above or add custom below.
            </p>
          ) : (
            Object.entries(parameters).map(([key, value]) => (
              <ParameterRow
                key={key}
                paramKey={key}
                value={value}
                onChange={(val) => handleUpdateParam(key, val)}
                onRemove={() => handleRemoveParam(key)}
              />
            ))
          )}
        </div>

        {/* Add Custom Parameter */}
        <div className="border-t border-slate-mid pt-4 mb-4">
          <p className="text-xs text-text-muted mb-3">Add custom parameter:</p>
          <div className="flex flex-col sm:flex-row gap-2">
            <input
              type="text"
              placeholder="Parameter name (e.g. clipSkip)"
              value={newKey}
              onChange={(e) => setNewKey(e.target.value)}
              className={clsx(
                "flex-1 px-3 py-2.5 rounded-lg",
                "bg-obsidian border border-slate-mid",
                "text-text-primary text-sm",
                "focus:outline-none focus:border-synapse",
                "transition-colors duration-200"
              )}
            />
            <input
              type="text"
              placeholder="Value"
              value={newValue}
              onChange={(e) => setNewValue(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === 'Enter' && newKey.trim()) {
                  handleAddCustomParam()
                }
              }}
              className={clsx(
                "flex-1 px-3 py-2.5 rounded-lg",
                "bg-obsidian border border-slate-mid",
                "text-text-primary text-sm",
                "focus:outline-none focus:border-synapse",
                "transition-colors duration-200"
              )}
            />
            <button
              onClick={handleAddCustomParam}
              disabled={!newKey.trim()}
              className={clsx(
                "px-6 py-2.5 rounded-lg font-semibold whitespace-nowrap",
                "bg-synapse hover:bg-synapse/80 text-obsidian",
                "disabled:bg-slate-mid disabled:text-text-muted",
                "transition-colors duration-200"
              )}
            >
              + Add
            </button>
          </div>
        </div>

        {/* Actions */}
        <div className="flex gap-3 pt-2">
          <Button
            variant="secondary"
            className="flex-1"
            onClick={onClose}
          >
            Cancel
          </Button>
          <Button
            className="flex-1"
            onClick={handleSave}
            disabled={isSaving}
          >
            {isSaving ? (
              <Loader2 className="w-5 h-5 animate-spin" />
            ) : (
              'Save'
            )}
          </Button>
        </div>
      </div>
    </div>
  )
}

export default EditParametersModal
