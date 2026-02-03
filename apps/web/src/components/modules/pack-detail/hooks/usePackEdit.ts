/**
 * usePackEdit Hook
 *
 * Manages pack edit mode state including:
 * - Edit mode toggle (global and per-section)
 * - Unsaved changes tracking
 * - Field-level state management
 * - Save/discard operations
 *
 * PHILOSOPHY:
 * - Single source of truth for edit state
 * - Optimistic updates with rollback on error
 * - Warn before losing unsaved changes
 */

import { useState, useCallback, useRef, useEffect } from 'react'
import type { PackDetail, PackSection, ValidationResult } from '../types'

// =============================================================================
// Types
// =============================================================================

export interface FieldChange {
  path: string
  oldValue: unknown
  newValue: unknown
  timestamp: number
}

export interface UsePackEditOptions {
  /**
   * Initial pack data for comparison
   */
  initialPack?: PackDetail

  /**
   * Callback when save is triggered
   */
  onSave?: (changes: Partial<PackDetail>) => Promise<void>

  /**
   * Callback when edit mode changes
   */
  onEditModeChange?: (isEditing: boolean) => void

  /**
   * Custom validation function
   */
  validate?: (changes: Partial<PackDetail>) => ValidationResult

  /**
   * Auto-save interval in ms (0 = disabled)
   */
  autoSaveInterval?: number
}

export interface UsePackEditReturn {
  // State
  isEditing: boolean
  isGlobalEdit: boolean
  editingSection: PackSection | null
  hasUnsavedChanges: boolean
  isSaving: boolean
  saveError: string | null

  // Pending changes
  pendingChanges: Partial<PackDetail>
  changeHistory: FieldChange[]

  // Actions
  startEditing: (section?: PackSection) => void
  stopEditing: () => void
  saveChanges: () => Promise<boolean>
  discardChanges: () => void

  // Field-level operations
  setFieldValue: <T>(path: string, value: T) => void
  getFieldValue: <T>(path: string, defaultValue?: T) => T
  getFieldError: (path: string) => string | null
  hasFieldChanged: (path: string) => boolean

  // Validation
  errors: Record<string, string>
  isValid: boolean
  validateAll: () => ValidationResult
}

// =============================================================================
// Utility Functions
// =============================================================================

/**
 * Get nested value from object by dot-notation path
 */
function getNestedValue<T>(obj: Record<string, unknown>, path: string, defaultValue?: T): T {
  const keys = path.split('.')
  let current: unknown = obj

  for (const key of keys) {
    if (current === null || current === undefined) {
      return defaultValue as T
    }
    current = (current as Record<string, unknown>)[key]
  }

  return (current ?? defaultValue) as T
}

/**
 * Set nested value in object by dot-notation path (immutable)
 */
function setNestedValue<T extends Record<string, unknown>>(
  obj: T,
  path: string,
  value: unknown
): T {
  const keys = path.split('.')
  const result = { ...obj }
  let current: Record<string, unknown> = result

  for (let i = 0; i < keys.length - 1; i++) {
    const key = keys[i]
    current[key] = { ...(current[key] as Record<string, unknown> || {}) }
    current = current[key] as Record<string, unknown>
  }

  current[keys[keys.length - 1]] = value
  return result as T
}

/**
 * Deep compare two values
 */
function deepEqual(a: unknown, b: unknown): boolean {
  if (a === b) return true
  if (a === null || b === null) return a === b
  if (typeof a !== typeof b) return false
  if (typeof a !== 'object') return a === b

  const aObj = a as Record<string, unknown>
  const bObj = b as Record<string, unknown>

  const aKeys = Object.keys(aObj)
  const bKeys = Object.keys(bObj)

  if (aKeys.length !== bKeys.length) return false

  return aKeys.every(key => deepEqual(aObj[key], bObj[key]))
}

// =============================================================================
// Main Hook
// =============================================================================

export function usePackEdit(options: UsePackEditOptions = {}): UsePackEditReturn {
  const {
    initialPack,
    onSave,
    onEditModeChange,
    validate,
    autoSaveInterval = 0,
  } = options

  // Core state
  const [isEditing, setIsEditing] = useState(false)
  const [editingSection, setEditingSection] = useState<PackSection | null>(null)
  const [pendingChanges, setPendingChanges] = useState<Partial<PackDetail>>({})
  const [changeHistory, setChangeHistory] = useState<FieldChange[]>([])
  const [errors, setErrors] = useState<Record<string, string>>({})
  const [isSaving, setIsSaving] = useState(false)
  const [saveError, setSaveError] = useState<string | null>(null)

  // Refs for comparison
  const initialPackRef = useRef<PackDetail | undefined>(initialPack)
  const autoSaveTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null)

  // Update initial pack ref when it changes
  useEffect(() => {
    if (initialPack && !isEditing) {
      initialPackRef.current = initialPack
    }
  }, [initialPack, isEditing])

  // Computed values
  const hasUnsavedChanges = Object.keys(pendingChanges).length > 0
  const isGlobalEdit = isEditing && editingSection === null

  // Validation
  const validateAll = useCallback((): ValidationResult => {
    if (validate) {
      return validate(pendingChanges)
    }
    // Default validation - always valid
    return { valid: true, errors: {} }
  }, [pendingChanges, validate])

  const isValid = Object.keys(errors).length === 0

  // Auto-save logic
  useEffect(() => {
    if (autoSaveInterval > 0 && hasUnsavedChanges && isEditing) {
      if (autoSaveTimerRef.current) {
        clearTimeout(autoSaveTimerRef.current)
      }
      autoSaveTimerRef.current = setTimeout(() => {
        // Auto-save would go here
        console.log('[usePackEdit] Auto-save triggered')
      }, autoSaveInterval)
    }

    return () => {
      if (autoSaveTimerRef.current) {
        clearTimeout(autoSaveTimerRef.current)
      }
    }
  }, [autoSaveInterval, hasUnsavedChanges, isEditing])

  // Start editing
  const startEditing = useCallback((section?: PackSection) => {
    setIsEditing(true)
    setEditingSection(section || null)
    setSaveError(null)
    onEditModeChange?.(true)
  }, [onEditModeChange])

  // Stop editing (without saving)
  const stopEditing = useCallback(() => {
    setIsEditing(false)
    setEditingSection(null)
    onEditModeChange?.(false)
  }, [onEditModeChange])

  // Save changes
  const saveChanges = useCallback(async (): Promise<boolean> => {
    if (!hasUnsavedChanges) {
      stopEditing()
      return true
    }

    // Validate before saving
    const validation = validateAll()
    if (!validation.valid) {
      setErrors(validation.errors)
      return false
    }

    setIsSaving(true)
    setSaveError(null)

    try {
      if (onSave) {
        await onSave(pendingChanges)
      }

      // Clear state on success
      setPendingChanges({})
      setChangeHistory([])
      setErrors({})
      stopEditing()

      return true
    } catch (error) {
      const message = error instanceof Error ? error.message : 'Failed to save changes'
      setSaveError(message)
      return false
    } finally {
      setIsSaving(false)
    }
  }, [hasUnsavedChanges, validateAll, onSave, pendingChanges, stopEditing])

  // Discard changes
  const discardChanges = useCallback(() => {
    setPendingChanges({})
    setChangeHistory([])
    setErrors({})
    setSaveError(null)
    stopEditing()
  }, [stopEditing])

  // Set field value
  const setFieldValue = useCallback(<T,>(path: string, value: T) => {
    // Get old value for history
    const oldValue = getNestedValue(
      pendingChanges as Record<string, unknown>,
      path,
      initialPackRef.current ? getNestedValue(initialPackRef.current as unknown as Record<string, unknown>, path) : undefined
    )

    // Skip if no change
    if (deepEqual(oldValue, value)) return

    // Record in history
    setChangeHistory(prev => [
      ...prev,
      { path, oldValue, newValue: value, timestamp: Date.now() }
    ])

    // Update pending changes
    setPendingChanges(prev =>
      setNestedValue(prev as Record<string, unknown>, path, value) as Partial<PackDetail>
    )

    // Clear error for this field
    setErrors(prev => {
      const next = { ...prev }
      delete next[path]
      return next
    })
  }, [pendingChanges])

  // Get field value (from pending changes or initial)
  const getFieldValue = useCallback(<T,>(path: string, defaultValue?: T): T => {
    // First check pending changes
    const pendingValue = getNestedValue<T>(
      pendingChanges as Record<string, unknown>,
      path
    )
    if (pendingValue !== undefined) return pendingValue

    // Fall back to initial pack
    if (initialPackRef.current) {
      return getNestedValue<T>(
        initialPackRef.current as unknown as Record<string, unknown>,
        path,
        defaultValue
      )
    }

    return defaultValue as T
  }, [pendingChanges])

  // Get field error
  const getFieldError = useCallback((path: string): string | null => {
    return errors[path] || null
  }, [errors])

  // Check if field has changed
  const hasFieldChanged = useCallback((path: string): boolean => {
    const currentValue = getNestedValue(pendingChanges as Record<string, unknown>, path)
    if (currentValue === undefined) return false

    if (!initialPackRef.current) return true

    const initialValue = getNestedValue(
      initialPackRef.current as unknown as Record<string, unknown>,
      path
    )

    return !deepEqual(currentValue, initialValue)
  }, [pendingChanges])

  return {
    // State
    isEditing,
    isGlobalEdit,
    editingSection,
    hasUnsavedChanges,
    isSaving,
    saveError,

    // Pending changes
    pendingChanges,
    changeHistory,

    // Actions
    startEditing,
    stopEditing,
    saveChanges,
    discardChanges,

    // Field-level
    setFieldValue,
    getFieldValue,
    getFieldError,
    hasFieldChanged,

    // Validation
    errors,
    isValid,
    validateAll,
  }
}

export default usePackEdit
