/**
 * EditableTags Component
 *
 * Inline editable tags component with add/remove functionality.
 *
 * Features:
 * - Click tag to remove (in edit mode)
 * - Add new tags via input
 * - Suggested tags dropdown
 * - Premium chip styling
 */

import { useState, useRef, type KeyboardEvent } from 'react'
import { useTranslation } from 'react-i18next'
import { X, Plus, Tag } from 'lucide-react'
import { clsx } from 'clsx'

// =============================================================================
// Types
// =============================================================================

export interface EditableTagsProps {
  /**
   * Current tags
   */
  tags: string[]

  /**
   * Callback when tags change
   */
  onChange: (tags: string[]) => void

  /**
   * Whether editing is enabled
   */
  editable?: boolean

  /**
   * Suggested tags to show
   */
  suggestions?: string[]

  /**
   * Maximum number of tags
   */
  maxTags?: number

  /**
   * Placeholder for input
   */
  placeholder?: string

  /**
   * Label for accessibility
   */
  label?: string

  /**
   * Additional className
   */
  className?: string

  /**
   * Variant for styling
   */
  variant?: 'default' | 'compact'
}

// =============================================================================
// Component
// =============================================================================

export function EditableTags({
  tags,
  onChange,
  editable = true,
  suggestions = [],
  maxTags,
  placeholder,
  label,
  className,
  variant = 'default',
}: EditableTagsProps) {
  const { t } = useTranslation()
  const resolvedPlaceholder = placeholder ?? t('pack.shared.editableTags.placeholder')
  const [inputValue, setInputValue] = useState('')
  const [showSuggestions, setShowSuggestions] = useState(false)
  const inputRef = useRef<HTMLInputElement>(null)

  // Filter suggestions (not already in tags)
  const filteredSuggestions = suggestions.filter(
    (s) => !tags.includes(s) && s.toLowerCase().includes(inputValue.toLowerCase())
  )

  // Handle adding a tag
  const addTag = (tag: string) => {
    const trimmed = tag.trim().toLowerCase()
    if (!trimmed) return
    if (tags.includes(trimmed)) return
    if (maxTags && tags.length >= maxTags) return

    onChange([...tags, trimmed])
    setInputValue('')
    setShowSuggestions(false)
  }

  // Handle removing a tag
  const removeTag = (tag: string) => {
    onChange(tags.filter((t) => t !== tag))
  }

  // Handle key events
  const handleKeyDown = (e: KeyboardEvent<HTMLInputElement>) => {
    if (e.key === 'Enter') {
      e.preventDefault()
      addTag(inputValue)
    } else if (e.key === 'Backspace' && !inputValue && tags.length > 0) {
      // Remove last tag on backspace when input is empty
      removeTag(tags[tags.length - 1])
    } else if (e.key === 'Escape') {
      setInputValue('')
      setShowSuggestions(false)
      inputRef.current?.blur()
    }
  }

  // Get tag style based on tag name
  const getTagStyle = (tag: string) => {
    if (tag === 'nsfw-pack' || tag === 'nsfw-pack-hide') {
      return 'bg-red-500/20 text-red-400 border-red-500/30'
    }
    if (tag.startsWith('style:')) {
      return 'bg-purple-500/20 text-purple-400 border-purple-500/30'
    }
    if (tag.startsWith('subject:')) {
      return 'bg-blue-500/20 text-blue-400 border-blue-500/30'
    }
    return 'bg-synapse/20 text-synapse border-synapse/30'
  }

  const isCompact = variant === 'compact'

  return (
    <div className={clsx('relative', className)}>
      {label && (
        <label className="block text-xs text-text-muted mb-2">
          {label}
        </label>
      )}

      {/* Tags container */}
      <div className={clsx(
        'flex flex-wrap gap-2',
        editable && 'pb-2'
      )}>
        {tags.map((tag) => (
          <span
            key={tag}
            className={clsx(
              'inline-flex items-center gap-1',
              isCompact ? 'px-2 py-0.5 text-xs' : 'px-3 py-1 text-sm',
              'rounded-lg border font-medium',
              'transition-all duration-200',
              getTagStyle(tag),
              editable && 'cursor-pointer hover:scale-105'
            )}
            onClick={() => editable && removeTag(tag)}
            role={editable ? 'button' : undefined}
            title={editable ? `Remove ${tag}` : undefined}
          >
            <Tag className={clsx(isCompact ? 'w-3 h-3' : 'w-3.5 h-3.5')} />
            {tag}
            {editable && (
              <X className={clsx(
                isCompact ? 'w-3 h-3' : 'w-3.5 h-3.5',
                'opacity-60 hover:opacity-100'
              )} />
            )}
          </span>
        ))}

        {/* Empty state */}
        {tags.length === 0 && !editable && (
          <span className="text-text-muted text-sm italic">{t('pack.shared.editableTags.noTags')}</span>
        )}
      </div>

      {/* Add tag input */}
      {editable && (!maxTags || tags.length < maxTags) && (
        <div className="relative mt-2">
          <div className="relative">
            <Plus className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-text-muted" />
            <input
              ref={inputRef}
              type="text"
              value={inputValue}
              onChange={(e) => {
                setInputValue(e.target.value)
                setShowSuggestions(true)
              }}
              onFocus={() => setShowSuggestions(true)}
              onBlur={() => {
                // Delay to allow click on suggestion
                setTimeout(() => setShowSuggestions(false), 200)
              }}
              onKeyDown={handleKeyDown}
              placeholder={resolvedPlaceholder}
              className={clsx(
                'w-full pl-9 pr-3 py-2 rounded-lg',
                'bg-slate-dark border border-slate-mid',
                'text-text-primary placeholder:text-text-muted',
                'focus:outline-none focus:border-synapse focus:ring-1 focus:ring-synapse/30',
                'transition-all duration-200',
                isCompact && 'text-sm py-1.5'
              )}
            />
          </div>

          {/* Suggestions dropdown */}
          {showSuggestions && filteredSuggestions.length > 0 && (
            <div className={clsx(
              'absolute top-full left-0 right-0 mt-1 z-10',
              'bg-slate-deep border border-slate-mid rounded-lg',
              'shadow-lg overflow-hidden',
              'max-h-48 overflow-y-auto'
            )}>
              {filteredSuggestions.map((suggestion) => (
                <button
                  key={suggestion}
                  type="button"
                  onClick={() => addTag(suggestion)}
                  className={clsx(
                    'w-full px-3 py-2 text-left text-sm',
                    'text-text-secondary hover:text-text-primary',
                    'hover:bg-slate-mid/50 transition-colors',
                    'flex items-center gap-2'
                  )}
                >
                  <Tag className="w-3.5 h-3.5 text-text-muted" />
                  {suggestion}
                </button>
              ))}
            </div>
          )}
        </div>
      )}

      {/* Max tags hint */}
      {maxTags && editable && (
        <div className={clsx(
          'text-xs mt-1',
          tags.length >= maxTags ? 'text-amber-400' : 'text-text-muted'
        )}>
          {t('pack.shared.editableTags.tagCount', { current: tags.length, max: maxTags })}
        </div>
      )}
    </div>
  )
}

export default EditableTags
