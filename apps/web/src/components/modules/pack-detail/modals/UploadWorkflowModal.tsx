/**
 * UploadWorkflowModal
 *
 * Modal for uploading ComfyUI workflow files.
 *
 * FUNKCE ZACHOVÁNY:
 * - File input (.json only)
 * - Auto-populate name from filename
 * - Optional description field
 * - Upload with loading state
 *
 * VIZUÁLNĚ VYLEPŠENO:
 * - Premium modal design
 * - Enhanced file input styling
 * - Better form layout
 */

import { useState, useEffect } from 'react'
import { X, Loader2, Upload } from 'lucide-react'
import { clsx } from 'clsx'
import { Button } from '@/components/ui/Button'
import { ANIMATION_PRESETS } from '../constants'

// =============================================================================
// Types
// =============================================================================

export interface UploadWorkflowModalProps {
  /**
   * Whether modal is open
   */
  isOpen: boolean

  /**
   * Handler for upload action
   */
  onUpload: (data: { file: File; name: string; description?: string }) => void

  /**
   * Handler for close/cancel
   */
  onClose: () => void

  /**
   * Whether upload is in progress
   */
  isUploading?: boolean
}

// =============================================================================
// Main Component
// =============================================================================

export function UploadWorkflowModal({
  isOpen,
  onUpload,
  onClose,
  isUploading = false,
}: UploadWorkflowModalProps) {
  const [file, setFile] = useState<File | null>(null)
  const [name, setName] = useState('')
  const [description, setDescription] = useState('')

  // Reset form when modal opens
  useEffect(() => {
    if (isOpen) {
      setFile(null)
      setName('')
      setDescription('')
    }
  }, [isOpen])

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const selectedFile = e.target.files?.[0]
    if (selectedFile) {
      setFile(selectedFile)
      // Auto-populate name from filename if name is empty
      if (!name) {
        setName(selectedFile.name.replace('.json', ''))
      }
    }
  }

  const handleSubmit = () => {
    if (file && name) {
      onUpload({
        file,
        name,
        description: description || undefined,
      })
    }
  }

  if (!isOpen) return null

  return (
    <div
      className={clsx(
        "fixed inset-0 bg-black/70 z-50",
        "flex items-center justify-center p-4",
        ANIMATION_PRESETS.fadeIn
      )}
      onClick={(e) => {
        if (e.target === e.currentTarget) onClose()
      }}
    >
      <div
        className={clsx(
          "bg-slate-deep rounded-2xl p-6 max-w-lg w-full",
          "border border-slate-mid/50",
          "shadow-2xl",
          ANIMATION_PRESETS.scaleIn
        )}
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div className="flex items-center justify-between mb-6">
          <h3 className="text-lg font-semibold text-text-primary">Upload Workflow</h3>
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

        {/* Form */}
        <div className="space-y-4">
          {/* File Input */}
          <div>
            <label className="block text-sm text-text-secondary mb-2">
              Workflow File (.json)
            </label>
            <input
              type="file"
              accept=".json"
              onChange={handleFileChange}
              className={clsx(
                "w-full px-3 py-2.5 rounded-lg",
                "bg-slate-dark border border-slate-mid",
                "text-text-primary",
                "file:mr-4 file:py-1.5 file:px-4",
                "file:rounded-lg file:border-0",
                "file:bg-synapse/20 file:text-synapse file:font-medium",
                "file:cursor-pointer file:transition-colors file:duration-200",
                "hover:file:bg-synapse/30",
                "focus:outline-none focus:border-synapse",
                "transition-colors duration-200"
              )}
            />
            {file && (
              <p className="text-xs text-text-muted mt-1">
                Selected: {file.name} ({(file.size / 1024).toFixed(1)} KB)
              </p>
            )}
          </div>

          {/* Workflow Name */}
          <div>
            <label className="block text-sm text-text-secondary mb-2">
              Workflow Name
            </label>
            <input
              type="text"
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="My Custom Workflow"
              className={clsx(
                "w-full px-4 py-2.5 rounded-lg",
                "bg-slate-dark border border-slate-mid",
                "text-text-primary placeholder:text-text-muted",
                "focus:outline-none focus:border-synapse",
                "transition-colors duration-200"
              )}
            />
          </div>

          {/* Description (optional) */}
          <div>
            <label className="block text-sm text-text-secondary mb-2">
              Description <span className="text-text-muted">(optional)</span>
            </label>
            <textarea
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              placeholder="Describe what this workflow does..."
              rows={3}
              className={clsx(
                "w-full px-4 py-2.5 rounded-lg resize-none",
                "bg-slate-dark border border-slate-mid",
                "text-text-primary placeholder:text-text-muted",
                "focus:outline-none focus:border-synapse",
                "transition-colors duration-200"
              )}
            />
          </div>
        </div>

        {/* Actions */}
        <div className="flex justify-end gap-3 mt-6">
          <Button
            variant="secondary"
            onClick={onClose}
          >
            Cancel
          </Button>
          <Button
            variant="primary"
            disabled={!file || !name || isUploading}
            onClick={handleSubmit}
          >
            {isUploading ? (
              <Loader2 className="w-4 h-4 animate-spin" />
            ) : (
              <Upload className="w-4 h-4" />
            )}
            Upload
          </Button>
        </div>
      </div>
    </div>
  )
}

export default UploadWorkflowModal
