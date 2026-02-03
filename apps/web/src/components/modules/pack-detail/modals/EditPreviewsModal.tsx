/**
 * EditPreviewsModal
 *
 * Modal for managing pack preview images/videos.
 *
 * Features:
 * - Drag & drop reordering
 * - Add preview (upload or URL)
 * - Remove preview (with confirmation)
 * - Set as cover image
 * - Preview thumbnails
 */

import { useState, useRef, useEffect } from 'react'
import {
  X,
  Loader2,
  GripVertical,
  Trash2,
  Star,
  Plus,
  Image,
  Link,
  Upload,
  Play,
  AlertCircle,
} from 'lucide-react'
import { clsx } from 'clsx'
import { Button } from '@/components/ui/Button'
import type { PreviewInfo } from '../types'
import { ANIMATION_PRESETS } from '../constants'

// =============================================================================
// Types
// =============================================================================

export interface EditPreviewsModalProps {
  /**
   * Whether modal is open
   */
  isOpen: boolean

  /**
   * Current previews
   */
  previews: PreviewInfo[]

  /**
   * Current cover URL
   */
  coverUrl?: string

  /**
   * Handler for saving changes
   */
  onSave: (data: {
    previews: PreviewInfo[]
    coverUrl?: string
    addedFiles?: File[]
    removedIndices?: number[]
  }) => void

  /**
   * Handler for close/cancel
   */
  onClose: () => void

  /**
   * Whether saving is in progress
   */
  isSaving?: boolean
}

// =============================================================================
// Preview Item Component
// =============================================================================

interface PreviewItemProps {
  preview: PreviewInfo
  index: number
  isCover: boolean
  isDragging: boolean
  onSetCover: () => void
  onRemove: () => void
  onDragStart: () => void
  onDragEnd: () => void
  onDragOver: (e: React.DragEvent) => void
  onDrop: (e: React.DragEvent) => void
}

function PreviewItem({
  preview,
  index,
  isCover,
  isDragging,
  onSetCover,
  onRemove,
  onDragStart,
  onDragEnd,
  onDragOver,
  onDrop,
}: PreviewItemProps) {
  const isVideo = preview.media_type === 'video'

  return (
    <div
      draggable
      onDragStart={onDragStart}
      onDragEnd={onDragEnd}
      onDragOver={onDragOver}
      onDrop={onDrop}
      className={clsx(
        'relative group rounded-xl overflow-hidden',
        'border-2 transition-all duration-200',
        isDragging
          ? 'opacity-50 border-synapse scale-95'
          : isCover
            ? 'border-synapse shadow-lg shadow-synapse/20'
            : 'border-slate-mid hover:border-slate-light',
        'cursor-grab active:cursor-grabbing'
      )}
    >
      {/* Thumbnail */}
      <div className="aspect-square bg-slate-dark">
        {isVideo ? (
          <div className="relative w-full h-full">
            {preview.thumbnail_url ? (
              <img
                src={preview.thumbnail_url}
                alt={`Preview ${index + 1}`}
                className="w-full h-full object-cover"
              />
            ) : (
              <div className="w-full h-full flex items-center justify-center bg-slate-mid">
                <Play className="w-8 h-8 text-text-muted" />
              </div>
            )}
            <div className="absolute bottom-2 right-2 px-2 py-0.5 rounded bg-black/70 text-xs text-white">
              Video
            </div>
          </div>
        ) : (
          <img
            src={preview.url || `/api/packs/${encodeURIComponent(preview.filename)}/preview`}
            alt={`Preview ${index + 1}`}
            className="w-full h-full object-cover"
          />
        )}
      </div>

      {/* Drag handle */}
      <div className={clsx(
        'absolute top-2 left-2 p-1.5 rounded-lg',
        'bg-black/50 text-white',
        'opacity-0 group-hover:opacity-100 transition-opacity'
      )}>
        <GripVertical className="w-4 h-4" />
      </div>

      {/* Cover badge */}
      {isCover && (
        <div className={clsx(
          'absolute top-2 right-2 px-2 py-1 rounded-lg',
          'bg-synapse/90 text-white text-xs font-medium',
          'flex items-center gap-1'
        )}>
          <Star className="w-3 h-3 fill-current" />
          Cover
        </div>
      )}

      {/* Actions overlay */}
      <div className={clsx(
        'absolute inset-0 bg-black/60',
        'opacity-0 group-hover:opacity-100',
        'transition-opacity duration-200',
        'flex items-center justify-center gap-2'
      )}>
        {!isCover && (
          <button
            onClick={(e) => {
              e.stopPropagation()
              onSetCover()
            }}
            className={clsx(
              'p-2 rounded-lg',
              'bg-synapse/80 text-white',
              'hover:bg-synapse transition-colors'
            )}
            title="Set as cover"
          >
            <Star className="w-5 h-5" />
          </button>
        )}
        <button
          onClick={(e) => {
            e.stopPropagation()
            onRemove()
          }}
          className={clsx(
            'p-2 rounded-lg',
            'bg-red-500/80 text-white',
            'hover:bg-red-500 transition-colors'
          )}
          title="Remove preview"
        >
          <Trash2 className="w-5 h-5" />
        </button>
      </div>

      {/* Index badge */}
      <div className={clsx(
        'absolute bottom-2 left-2 px-2 py-0.5 rounded',
        'bg-black/70 text-white text-xs'
      )}>
        #{index + 1}
      </div>
    </div>
  )
}

// =============================================================================
// Add Preview Panel
// =============================================================================

interface AddPreviewPanelProps {
  onAddFile: (file: File) => void
  onAddUrl: (url: string) => void
}

function AddPreviewPanel({ onAddFile, onAddUrl }: AddPreviewPanelProps) {
  const [mode, setMode] = useState<'upload' | 'url'>('upload')
  const [urlInput, setUrlInput] = useState('')
  const [urlError, setUrlError] = useState<string | null>(null)
  const [isDragging, setIsDragging] = useState(false)
  const fileInputRef = useRef<HTMLInputElement>(null)
  const dragCounterRef = useRef(0)

  const handleFileSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (file) {
      onAddFile(file)
      e.target.value = '' // Reset input
    }
  }

  // Drag & drop handlers
  const handleDragEnter = (e: React.DragEvent) => {
    e.preventDefault()
    e.stopPropagation()
    dragCounterRef.current++
    if (e.dataTransfer.types.includes('Files')) {
      setIsDragging(true)
    }
  }

  const handleDragLeave = (e: React.DragEvent) => {
    e.preventDefault()
    e.stopPropagation()
    dragCounterRef.current--
    if (dragCounterRef.current === 0) {
      setIsDragging(false)
    }
  }

  const handleDragOver = (e: React.DragEvent) => {
    e.preventDefault()
    e.stopPropagation()
  }

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault()
    e.stopPropagation()
    setIsDragging(false)
    dragCounterRef.current = 0

    const files = e.dataTransfer.files
    if (files.length > 0) {
      // Add all dropped files
      Array.from(files).forEach(file => {
        if (file.type.startsWith('image/') || file.type.startsWith('video/')) {
          onAddFile(file)
        }
      })
    }
  }

  const handleUrlSubmit = () => {
    if (!urlInput.trim()) {
      setUrlError('Please enter a URL')
      return
    }
    try {
      new URL(urlInput)
      onAddUrl(urlInput)
      setUrlInput('')
      setUrlError(null)
    } catch {
      setUrlError('Invalid URL format')
    }
  }

  return (
    <div className="border border-dashed border-slate-mid rounded-xl p-4">
      {/* Mode tabs */}
      <div className="flex gap-2 mb-4">
        <button
          onClick={() => setMode('upload')}
          className={clsx(
            'flex-1 py-2 px-4 rounded-lg text-sm font-medium',
            'transition-colors duration-200',
            mode === 'upload'
              ? 'bg-synapse/20 text-synapse border border-synapse/30'
              : 'bg-slate-mid/50 text-text-muted hover:text-text-secondary'
          )}
        >
          <Upload className="w-4 h-4 inline-block mr-2" />
          Upload
        </button>
        <button
          onClick={() => setMode('url')}
          className={clsx(
            'flex-1 py-2 px-4 rounded-lg text-sm font-medium',
            'transition-colors duration-200',
            mode === 'url'
              ? 'bg-synapse/20 text-synapse border border-synapse/30'
              : 'bg-slate-mid/50 text-text-muted hover:text-text-secondary'
          )}
        >
          <Link className="w-4 h-4 inline-block mr-2" />
          URL
        </button>
      </div>

      {mode === 'upload' ? (
        <div
          onClick={() => fileInputRef.current?.click()}
          onDragEnter={handleDragEnter}
          onDragLeave={handleDragLeave}
          onDragOver={handleDragOver}
          onDrop={handleDrop}
          className={clsx(
            'flex flex-col items-center justify-center gap-2',
            'py-8 rounded-lg cursor-pointer',
            'border-2 border-dashed',
            'transition-all duration-200',
            isDragging
              ? 'bg-synapse/20 border-synapse scale-[1.02]'
              : 'bg-slate-dark/50 border-slate-mid hover:bg-slate-dark hover:border-synapse/50'
          )}
        >
          <Image className={clsx('w-8 h-8', isDragging ? 'text-synapse' : 'text-text-muted')} />
          <span className={clsx('text-sm', isDragging ? 'text-synapse font-medium' : 'text-text-secondary')}>
            {isDragging ? 'Drop files here' : 'Click or drag files here'}
          </span>
          <span className="text-xs text-text-muted">
            JPG, PNG, GIF, WEBP, MP4
          </span>
          <input
            ref={fileInputRef}
            type="file"
            accept="image/*,video/*"
            multiple
            onChange={handleFileSelect}
            className="hidden"
          />
        </div>
      ) : (
        <div className="space-y-2">
          <div className="flex gap-2">
            <input
              type="url"
              value={urlInput}
              onChange={(e) => {
                setUrlInput(e.target.value)
                setUrlError(null)
              }}
              onKeyDown={(e) => e.key === 'Enter' && handleUrlSubmit()}
              placeholder="https://example.com/image.jpg"
              className={clsx(
                'flex-1 px-4 py-2 rounded-lg',
                'bg-slate-dark border',
                'text-text-primary placeholder:text-text-muted',
                'focus:outline-none focus:ring-1',
                urlError
                  ? 'border-red-500 focus:ring-red-500/30'
                  : 'border-slate-mid focus:border-synapse focus:ring-synapse/30',
                'transition-colors duration-200'
              )}
            />
            <Button variant="primary" onClick={handleUrlSubmit}>
              <Plus className="w-4 h-4" />
              Add
            </Button>
          </div>
          {urlError && (
            <div className="flex items-center gap-1 text-xs text-red-400">
              <AlertCircle className="w-3 h-3" />
              {urlError}
            </div>
          )}
        </div>
      )}
    </div>
  )
}

// =============================================================================
// Main Component
// =============================================================================

export function EditPreviewsModal({
  isOpen,
  previews: initialPreviews,
  coverUrl: initialCoverUrl,
  onSave,
  onClose,
  isSaving = false,
}: EditPreviewsModalProps) {
  const [previews, setPreviews] = useState<PreviewInfo[]>(initialPreviews)
  const [coverUrl, setCoverUrl] = useState<string | undefined>(initialCoverUrl)
  const [addedFiles, setAddedFiles] = useState<File[]>([])
  const [removedIndices, setRemovedIndices] = useState<number[]>([])
  const [draggedIndex, setDraggedIndex] = useState<number | null>(null)

  // Reset state when modal opens
  useEffect(() => {
    if (isOpen) {
      setPreviews(initialPreviews)
      setCoverUrl(initialCoverUrl)
      setAddedFiles([])
      setRemovedIndices([])
    }
  }, [isOpen, initialPreviews, initialCoverUrl])

  // Handle drag start
  const handleDragStart = (index: number) => {
    setDraggedIndex(index)
  }

  // Handle drag end
  const handleDragEnd = () => {
    setDraggedIndex(null)
  }

  // Handle drag over
  const handleDragOver = (e: React.DragEvent, index: number) => {
    e.preventDefault()
    if (draggedIndex === null || draggedIndex === index) return

    // Reorder previews
    const newPreviews = [...previews]
    const draggedItem = newPreviews[draggedIndex]
    newPreviews.splice(draggedIndex, 1)
    newPreviews.splice(index, 0, draggedItem)
    setPreviews(newPreviews)
    setDraggedIndex(index)
  }

  // Handle drop
  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault()
    setDraggedIndex(null)
  }

  // Set cover
  const handleSetCover = (index: number) => {
    const preview = previews[index]
    setCoverUrl(preview.url || undefined)
  }

  // Remove preview
  const handleRemove = (index: number) => {
    const newPreviews = [...previews]
    const removed = newPreviews.splice(index, 1)[0]

    // Track removal for original previews
    if (!removed.url?.startsWith('blob:')) {
      setRemovedIndices([...removedIndices, index])
    }

    setPreviews(newPreviews)

    // Update cover if removed was cover
    if (removed.url === coverUrl) {
      setCoverUrl(newPreviews[0]?.url)
    }
  }

  // Add file
  const handleAddFile = (file: File) => {
    const newPreview: PreviewInfo = {
      filename: file.name,
      url: URL.createObjectURL(file),
      nsfw: false,
      media_type: file.type.startsWith('video/') ? 'video' : 'image',
    }
    setPreviews([...previews, newPreview])
    setAddedFiles([...addedFiles, file])
  }

  // Add URL
  const handleAddUrl = (url: string) => {
    const newPreview: PreviewInfo = {
      filename: url.split('/').pop() || 'preview',
      url,
      nsfw: false,
      media_type: url.includes('.mp4') || url.includes('.webm') ? 'video' : 'image',
    }
    setPreviews([...previews, newPreview])
  }

  // Handle save
  const handleSave = () => {
    onSave({
      previews,
      coverUrl,
      addedFiles: addedFiles.length > 0 ? addedFiles : undefined,
      removedIndices: removedIndices.length > 0 ? removedIndices : undefined,
    })
  }

  // Check if there are changes
  const hasChanges =
    JSON.stringify(previews) !== JSON.stringify(initialPreviews) ||
    coverUrl !== initialCoverUrl ||
    addedFiles.length > 0 ||
    removedIndices.length > 0

  if (!isOpen) return null

  // Prevent browser from opening files when dropping outside drop zone
  const preventBrowserDrop = (e: React.DragEvent) => {
    e.preventDefault()
    e.stopPropagation()
  }

  return (
    <div
      className={clsx(
        "fixed inset-0 bg-black/70 z-50",
        "flex items-center justify-center p-4",
        ANIMATION_PRESETS.fadeIn
      )}
      onDragOver={preventBrowserDrop}
      onDrop={preventBrowserDrop}
      onClick={(e) => {
        if (e.target === e.currentTarget) onClose()
      }}
    >
      <div
        className={clsx(
          "bg-slate-deep rounded-2xl max-w-4xl w-full max-h-[90vh]",
          "border border-slate-mid/50",
          "shadow-2xl flex flex-col",
          ANIMATION_PRESETS.scaleIn
        )}
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div className="flex items-center justify-between p-6 border-b border-slate-mid/50">
          <div>
            <h3 className="text-lg font-semibold text-text-primary">
              Edit Previews
            </h3>
            <p className="text-sm text-text-muted mt-1">
              Drag to reorder, click to set cover or remove
            </p>
          </div>
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

        {/* Content */}
        <div className="flex-1 overflow-y-auto p-6">
          {/* Previews grid */}
          {previews.length > 0 ? (
            <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 gap-4 mb-6">
              {previews.map((preview, index) => (
                <PreviewItem
                  key={preview.url || index}
                  preview={preview}
                  index={index}
                  isCover={preview.url === coverUrl || (index === 0 && !coverUrl)}
                  isDragging={draggedIndex === index}
                  onSetCover={() => handleSetCover(index)}
                  onRemove={() => handleRemove(index)}
                  onDragStart={() => handleDragStart(index)}
                  onDragEnd={handleDragEnd}
                  onDragOver={(e) => handleDragOver(e, index)}
                  onDrop={handleDrop}
                />
              ))}
            </div>
          ) : (
            <div className="text-center py-12 text-text-muted mb-6">
              <Image className="w-12 h-12 mx-auto mb-3 opacity-50" />
              <p>No previews yet</p>
            </div>
          )}

          {/* Add preview panel */}
          <AddPreviewPanel
            onAddFile={handleAddFile}
            onAddUrl={handleAddUrl}
          />
        </div>

        {/* Footer */}
        <div className="flex justify-end gap-3 p-6 border-t border-slate-mid/50">
          <Button variant="secondary" onClick={onClose}>
            Cancel
          </Button>
          <Button
            variant="primary"
            disabled={!hasChanges || isSaving}
            onClick={handleSave}
          >
            {isSaving ? (
              <Loader2 className="w-4 h-4 animate-spin" />
            ) : null}
            Save Changes
          </Button>
        </div>
      </div>
    </div>
  )
}

export default EditPreviewsModal
