/**
 * EditableText Component
 *
 * Click-to-edit text component with inline editing support.
 * Supports single-line (input) and multi-line (textarea) modes.
 *
 * Features:
 * - Click to edit
 * - Enter to save (single-line)
 * - Escape to cancel
 * - Auto-focus on edit
 * - Validation support
 * - Premium styling with edit indicator
 */

import { useState, useRef, useEffect, useCallback, type KeyboardEvent } from 'react'
import { Pencil, Check, X, AlertCircle } from 'lucide-react'
import { clsx } from 'clsx'

// =============================================================================
// Types
// =============================================================================

export interface EditableTextProps {
  /**
   * Current value
   */
  value: string

  /**
   * Callback when value changes
   */
  onChange: (value: string) => void

  /**
   * Whether editing is enabled
   */
  editable?: boolean

  /**
   * Placeholder text when empty
   */
  placeholder?: string

  /**
   * Multi-line textarea mode
   */
  multiline?: boolean

  /**
   * Number of rows for multiline (default: 3)
   */
  rows?: number

  /**
   * Max length validation
   */
  maxLength?: number

  /**
   * Custom validation function
   */
  validate?: (value: string) => string | null

  /**
   * Error message to display
   */
  error?: string | null

  /**
   * Text variant for styling
   */
  variant?: 'title' | 'subtitle' | 'body' | 'small'

  /**
   * Additional className
   */
  className?: string

  /**
   * Whether the field is required
   */
  required?: boolean

  /**
   * Label for accessibility
   */
  label?: string
}

// =============================================================================
// Component
// =============================================================================

export function EditableText({
  value,
  onChange,
  editable = true,
  placeholder = 'Click to edit...',
  multiline = false,
  rows = 3,
  maxLength,
  validate,
  error: externalError,
  variant = 'body',
  className,
  required = false,
  label,
}: EditableTextProps) {
  const [isEditing, setIsEditing] = useState(false)
  const [editValue, setEditValue] = useState(value)
  const [localError, setLocalError] = useState<string | null>(null)
  const inputRef = useRef<HTMLInputElement | HTMLTextAreaElement>(null)

  // Sync edit value with prop value when not editing
  useEffect(() => {
    if (!isEditing) {
      setEditValue(value)
    }
  }, [value, isEditing])

  // Focus input when editing starts
  useEffect(() => {
    if (isEditing && inputRef.current) {
      inputRef.current.focus()
      // Select all text
      inputRef.current.select()
    }
  }, [isEditing])

  // Validate value
  const validateValue = useCallback((val: string): string | null => {
    if (required && !val.trim()) {
      return 'This field is required'
    }
    if (maxLength && val.length > maxLength) {
      return `Maximum ${maxLength} characters`
    }
    if (validate) {
      return validate(val)
    }
    return null
  }, [required, maxLength, validate])

  // Handle click to edit
  const handleClick = () => {
    if (editable && !isEditing) {
      setIsEditing(true)
      setLocalError(null)
    }
  }

  // Handle save
  const handleSave = () => {
    const error = validateValue(editValue)
    if (error) {
      setLocalError(error)
      return
    }

    onChange(editValue)
    setIsEditing(false)
    setLocalError(null)
  }

  // Handle cancel
  const handleCancel = () => {
    setEditValue(value)
    setIsEditing(false)
    setLocalError(null)
  }

  // Handle key events
  const handleKeyDown = (e: KeyboardEvent) => {
    if (e.key === 'Escape') {
      e.preventDefault()
      handleCancel()
    } else if (e.key === 'Enter' && !multiline) {
      e.preventDefault()
      handleSave()
    } else if (e.key === 'Enter' && e.metaKey && multiline) {
      // Cmd/Ctrl+Enter to save in multiline
      e.preventDefault()
      handleSave()
    }
  }

  // Variant styles
  const variantStyles = {
    title: 'text-2xl font-bold text-text-primary',
    subtitle: 'text-lg font-semibold text-text-primary',
    body: 'text-base text-text-secondary',
    small: 'text-sm text-text-muted',
  }

  const error = externalError || localError
  const isEmpty = !value.trim()

  // Edit mode
  if (isEditing) {
    const InputComponent = multiline ? 'textarea' : 'input'

    return (
      <div className={clsx('relative group', className)}>
        {label && (
          <label className="block text-xs text-text-muted mb-1">
            {label}
            {required && <span className="text-red-400 ml-0.5">*</span>}
          </label>
        )}

        <div className="relative">
          <InputComponent
            ref={inputRef as any}
            value={editValue}
            onChange={(e) => {
              setEditValue(e.target.value)
              setLocalError(null)
            }}
            onKeyDown={handleKeyDown}
            onBlur={handleSave}
            rows={multiline ? rows : undefined}
            maxLength={maxLength}
            className={clsx(
              'w-full px-3 py-2 rounded-lg',
              'bg-slate-dark border',
              'text-text-primary placeholder:text-text-muted',
              'focus:outline-none focus:ring-2',
              'transition-all duration-200',
              multiline && 'resize-none',
              error
                ? 'border-red-500 focus:ring-red-500/30'
                : 'border-synapse focus:ring-synapse/30',
              variantStyles[variant]
            )}
            placeholder={placeholder}
            aria-label={label}
          />

          {/* Action buttons */}
          <div className="absolute right-2 top-1/2 -translate-y-1/2 flex gap-1">
            <button
              type="button"
              onClick={(e) => {
                e.stopPropagation()
                handleSave()
              }}
              className={clsx(
                'p-1 rounded',
                'bg-synapse/20 text-synapse',
                'hover:bg-synapse/30 transition-colors'
              )}
              title="Save (Enter)"
            >
              <Check className="w-4 h-4" />
            </button>
            <button
              type="button"
              onClick={(e) => {
                e.stopPropagation()
                handleCancel()
              }}
              className={clsx(
                'p-1 rounded',
                'bg-slate-mid/50 text-text-muted',
                'hover:bg-slate-mid hover:text-text-primary transition-colors'
              )}
              title="Cancel (Esc)"
            >
              <X className="w-4 h-4" />
            </button>
          </div>
        </div>

        {/* Error message */}
        {error && (
          <div className="flex items-center gap-1 mt-1 text-xs text-red-400">
            <AlertCircle className="w-3 h-3" />
            {error}
          </div>
        )}

        {/* Character count */}
        {maxLength && (
          <div className={clsx(
            'text-right text-xs mt-1',
            editValue.length > maxLength * 0.9 ? 'text-amber-400' : 'text-text-muted'
          )}>
            {editValue.length}/{maxLength}
          </div>
        )}
      </div>
    )
  }

  // Display mode
  return (
    <div
      className={clsx(
        'group relative',
        editable && 'cursor-pointer',
        className
      )}
      onClick={handleClick}
      role={editable ? 'button' : undefined}
      tabIndex={editable ? 0 : undefined}
      onKeyDown={(e) => {
        if (editable && (e.key === 'Enter' || e.key === ' ')) {
          e.preventDefault()
          handleClick()
        }
      }}
      aria-label={label ? `${label}: ${value || placeholder}. ${editable ? 'Click to edit.' : ''}` : undefined}
    >
      {label && (
        <label className="block text-xs text-text-muted mb-1">
          {label}
          {required && <span className="text-red-400 ml-0.5">*</span>}
        </label>
      )}

      <div className={clsx(
        'relative',
        editable && [
          'px-3 py-2 rounded-lg',
          'border border-transparent',
          'transition-all duration-200',
          'hover:bg-white/5 hover:border-slate-mid',
          'group-focus:ring-2 group-focus:ring-synapse/30',
        ]
      )}>
        <span className={clsx(
          variantStyles[variant],
          isEmpty && 'text-text-muted italic'
        )}>
          {isEmpty ? placeholder : value}
        </span>

        {/* Edit indicator */}
        {editable && (
          <Pencil className={clsx(
            'absolute right-2 top-1/2 -translate-y-1/2',
            'w-4 h-4 text-text-muted',
            'opacity-0 group-hover:opacity-100',
            'transition-opacity duration-200'
          )} />
        )}
      </div>

      {/* External error display */}
      {error && !isEditing && (
        <div className="flex items-center gap-1 mt-1 text-xs text-red-400">
          <AlertCircle className="w-3 h-3" />
          {error}
        </div>
      )}
    </div>
  )
}

export default EditableText
