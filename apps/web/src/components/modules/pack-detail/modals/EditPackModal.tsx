/**
 * EditPackModal
 *
 * Modal for editing pack metadata (currently user tags).
 *
 * FUNKCE ZACHOVÁNY:
 * - User tags editor with removable chips
 * - Suggested tags with special nsfw-pack styling
 * - Custom tag input with Enter key support
 * - Save/Cancel actions with loading state
 *
 * VIZUÁLNĚ VYLEPŠENO:
 * - Premium modal design
 * - Enhanced tag chip styling
 * - Better focus states
 */

import { useState, useEffect } from 'react'
import { X, Loader2 } from 'lucide-react'
import { clsx } from 'clsx'
import { Button } from '@/components/ui/Button'
import { ANIMATION_PRESETS } from '../constants'

// =============================================================================
// Types
// =============================================================================

export interface EditPackModalProps {
  /**
   * Whether modal is open
   */
  isOpen: boolean

  /**
   * Initial tags to edit
   */
  initialTags: string[]

  /**
   * Handler for save action
   */
  onSave: (tags: string[]) => void

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

const SUGGESTED_TAGS = ['favorite', 'nsfw-pack', 'anime', 'realistic', 'style', 'character']

// =============================================================================
// Sub-components
// =============================================================================

interface TagChipProps {
  tag: string
  onRemove: () => void
}

function TagChip({ tag, onRemove }: TagChipProps) {
  const isNsfw = tag === 'nsfw-pack'

  return (
    <span
      className={clsx(
        "px-3 py-1.5 rounded-lg text-sm flex items-center gap-2",
        "transition-all duration-200",
        isNsfw
          ? "bg-red-500/20 text-red-400 border border-red-500/30"
          : "bg-pulse/20 text-pulse border border-pulse/30"
      )}
    >
      {tag}
      <button
        onClick={onRemove}
        className="hover:text-red-400 transition-colors"
        aria-label={`Remove ${tag} tag`}
      >
        <X className="w-3 h-3" />
      </button>
    </span>
  )
}

interface SuggestedTagButtonProps {
  tag: string
  isAdded: boolean
  onAdd: () => void
}

function SuggestedTagButton({ tag, isAdded, onAdd }: SuggestedTagButtonProps) {
  const isNsfw = tag === 'nsfw-pack'

  return (
    <button
      onClick={onAdd}
      disabled={isAdded}
      className={clsx(
        "px-2.5 py-1 rounded text-xs transition-all duration-200",
        isAdded
          ? "bg-slate-mid/30 text-text-muted cursor-not-allowed"
          : isNsfw
            ? "bg-red-500/10 text-red-400 hover:bg-red-500/20 hover:scale-105"
            : "bg-slate-mid/50 text-text-secondary hover:bg-slate-mid hover:scale-105"
      )}
    >
      + {tag}
    </button>
  )
}

// =============================================================================
// Main Component
// =============================================================================

export function EditPackModal({
  isOpen,
  initialTags,
  onSave,
  onClose,
  isSaving = false,
}: EditPackModalProps) {
  const [tags, setTags] = useState<string[]>(initialTags)
  const [newTag, setNewTag] = useState('')

  // Reset tags when modal opens with new initial values
  useEffect(() => {
    if (isOpen) {
      setTags(initialTags)
      setNewTag('')
    }
  }, [isOpen, initialTags])

  const handleAddTag = (tag: string) => {
    const trimmed = tag.trim()
    if (trimmed && !tags.includes(trimmed)) {
      setTags(prev => [...prev, trimmed])
    }
  }

  const handleRemoveTag = (index: number) => {
    setTags(prev => prev.filter((_, i) => i !== index))
  }

  const handleKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === 'Enter' && newTag.trim()) {
      e.preventDefault()
      handleAddTag(newTag)
      setNewTag('')
    }
  }

  if (!isOpen) return null

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
          "bg-slate-dark rounded-2xl p-6 max-w-lg w-full",
          "border border-slate-mid",
          "shadow-2xl",
          ANIMATION_PRESETS.scaleIn
        )}
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div className="flex items-center justify-between mb-6">
          <h2 className="text-xl font-bold text-text-primary">Edit Pack</h2>
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

        {/* User Tags Editor */}
        <div className="space-y-4">
          <div>
            <label className="block text-sm font-medium text-text-primary mb-3">
              User Tags
            </label>

            {/* Current Tags */}
            <div className="flex flex-wrap gap-2 mb-4 min-h-[40px]">
              {tags.length > 0 ? (
                tags.map((tag, idx) => (
                  <TagChip
                    key={idx}
                    tag={tag}
                    onRemove={() => handleRemoveTag(idx)}
                  />
                ))
              ) : (
                <p className="text-text-muted text-sm italic">No tags yet</p>
              )}
            </div>

            {/* Suggested Tags */}
            <div className="mb-4">
              <p className="text-xs text-text-muted mb-2">Suggested tags:</p>
              <div className="flex flex-wrap gap-2">
                {SUGGESTED_TAGS.map(suggested => (
                  <SuggestedTagButton
                    key={suggested}
                    tag={suggested}
                    isAdded={tags.includes(suggested)}
                    onAdd={() => handleAddTag(suggested)}
                  />
                ))}
              </div>
            </div>

            {/* Custom Tag Input */}
            <div className="flex gap-2">
              <input
                type="text"
                value={newTag}
                onChange={(e) => setNewTag(e.target.value)}
                onKeyDown={handleKeyDown}
                placeholder="Add tag and press Enter"
                className={clsx(
                  "flex-1 px-4 py-2.5 rounded-lg",
                  "bg-obsidian border border-slate-mid",
                  "text-text-primary placeholder:text-text-muted",
                  "focus:outline-none focus:border-synapse",
                  "transition-colors duration-200"
                )}
              />
              <Button
                onClick={() => {
                  if (newTag.trim()) {
                    handleAddTag(newTag)
                    setNewTag('')
                  }
                }}
                disabled={!newTag.trim()}
              >
                Add
              </Button>
            </div>
          </div>
        </div>

        {/* Actions */}
        <div className="flex gap-3 mt-6">
          <Button
            variant="secondary"
            className="flex-1"
            onClick={onClose}
          >
            Cancel
          </Button>
          <Button
            className="flex-1"
            onClick={() => onSave(tags)}
            disabled={isSaving}
          >
            {isSaving ? (
              <Loader2 className="w-5 h-5 animate-spin" />
            ) : (
              'Save Changes'
            )}
          </Button>
        </div>
      </div>
    </div>
  )
}

export default EditPackModal
