/**
 * CreatePackModal
 *
 * Modal wizard for creating a new custom pack from scratch.
 *
 * Features:
 * - Pack name and type selection
 * - Optional metadata (description, base model, author)
 * - Tags and trigger words
 * - Validation before creation
 * - i18n support
 */

import { useState, type KeyboardEvent } from 'react'
import { useTranslation } from 'react-i18next'
import {
  X,
  Loader2,
  Package,
  Plus,
  Tag,
  Sparkles,
  FileText,
  User,
  Hash,
} from 'lucide-react'
import { clsx } from 'clsx'
import { Button } from '@/components/ui/Button'
import { ANIMATION_PRESETS, ASSET_TYPE_ICONS } from '../constants'
import type { AssetType } from '../types'

// =============================================================================
// Types
// =============================================================================

export interface CreatePackModalProps {
  /**
   * Whether modal is open
   */
  isOpen: boolean

  /**
   * Handler for close/cancel
   */
  onClose: () => void

  /**
   * Handler for creating pack
   */
  onCreate: (data: CreatePackData) => Promise<void>

  /**
   * Whether creation is in progress
   */
  isCreating?: boolean
}

export interface CreatePackData {
  name: string
  pack_type: string
  description?: string
  base_model?: string
  version: string
  author?: string
  tags: string[]
  user_tags: string[]
  trigger_words: string[]
}

// =============================================================================
// Pack Type Options
// =============================================================================

const PACK_TYPES: { value: AssetType; labelKey: string }[] = [
  { value: 'lora', labelKey: 'LoRA' },
  { value: 'checkpoint', labelKey: 'Checkpoint' },
  { value: 'vae', labelKey: 'VAE' },
  { value: 'controlnet', labelKey: 'ControlNet' },
  { value: 'embedding', labelKey: 'Embedding' },
  { value: 'upscaler', labelKey: 'Upscaler' },
]

// =============================================================================
// Tag Input Component
// =============================================================================

interface TagInputProps {
  tags: string[]
  onChange: (tags: string[]) => void
  placeholder?: string
  label?: string
  hint?: string
}

function TagInput({ tags, onChange, placeholder, label, hint }: TagInputProps) {
  const [inputValue, setInputValue] = useState('')

  const addTag = (value: string) => {
    const trimmed = value.trim().toLowerCase()
    if (trimmed && !tags.includes(trimmed)) {
      onChange([...tags, trimmed])
    }
    setInputValue('')
  }

  const removeTag = (tag: string) => {
    onChange(tags.filter(t => t !== tag))
  }

  const handleKeyDown = (e: KeyboardEvent<HTMLInputElement>) => {
    if (e.key === 'Enter') {
      e.preventDefault()
      addTag(inputValue)
    } else if (e.key === 'Backspace' && !inputValue && tags.length > 0) {
      removeTag(tags[tags.length - 1])
    }
  }

  return (
    <div>
      {label && (
        <label className="block text-sm font-medium text-text-primary mb-1.5">
          {label}
        </label>
      )}
      <div className={clsx(
        'flex flex-wrap gap-2 p-3 rounded-lg',
        'bg-slate-dark border border-slate-mid',
        'focus-within:border-synapse focus-within:ring-1 focus-within:ring-synapse/30',
        'transition-all duration-200'
      )}>
        {tags.map(tag => (
          <span
            key={tag}
            className={clsx(
              'inline-flex items-center gap-1 px-2 py-0.5 rounded text-sm',
              'bg-synapse/20 text-synapse border border-synapse/30'
            )}
          >
            <Tag className="w-3 h-3" />
            {tag}
            <button
              type="button"
              onClick={() => removeTag(tag)}
              className="hover:text-red-400 transition-colors"
            >
              <X className="w-3 h-3" />
            </button>
          </span>
        ))}
        <input
          type="text"
          value={inputValue}
          onChange={(e) => setInputValue(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder={tags.length === 0 ? placeholder : ''}
          className={clsx(
            'flex-1 min-w-[120px] bg-transparent outline-none',
            'text-text-primary placeholder:text-text-muted'
          )}
        />
      </div>
      {hint && (
        <p className="text-xs text-text-muted mt-1">{hint}</p>
      )}
    </div>
  )
}

// =============================================================================
// Main Component
// =============================================================================

export function CreatePackModal({
  isOpen,
  onClose,
  onCreate,
  isCreating = false,
}: CreatePackModalProps) {
  const { t } = useTranslation()

  // Form state
  const [name, setName] = useState('')
  const [packType, setPackType] = useState<AssetType>('lora')
  const [description, setDescription] = useState('')
  const [baseModel, setBaseModel] = useState('')
  const [version, setVersion] = useState('1.0.0')
  const [author, setAuthor] = useState('')
  const [tags, setTags] = useState<string[]>([])
  const [triggerWords, setTriggerWords] = useState<string[]>([])
  const [error, setError] = useState<string | null>(null)

  // Validation
  const isValid = name.trim().length > 0

  // Handle create
  const handleCreate = async () => {
    if (!isValid) return

    setError(null)

    try {
      await onCreate({
        name: name.trim(),
        pack_type: packType,
        description: description.trim() || undefined,
        base_model: baseModel.trim() || undefined,
        version: version.trim() || '1.0.0',
        author: author.trim() || undefined,
        tags,
        user_tags: [],
        trigger_words: triggerWords,
      })
    } catch (err) {
      setError(err instanceof Error ? err.message : t('pack.modals.create.error'))
    }
  }

  // Reset form
  const handleClose = () => {
    setName('')
    setPackType('lora')
    setDescription('')
    setBaseModel('')
    setVersion('1.0.0')
    setAuthor('')
    setTags([])
    setTriggerWords([])
    setError(null)
    onClose()
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
        if (e.target === e.currentTarget) handleClose()
      }}
    >
      <div
        className={clsx(
          "bg-slate-deep rounded-2xl max-w-2xl w-full max-h-[90vh]",
          "border border-slate-mid/50",
          "shadow-2xl flex flex-col",
          ANIMATION_PRESETS.scaleIn
        )}
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div className="flex items-center justify-between p-6 border-b border-slate-mid/50">
          <div className="flex items-center gap-3">
            <div className="p-2 rounded-xl bg-synapse/20">
              <Package className="w-6 h-6 text-synapse" />
            </div>
            <div>
              <h3 className="text-lg font-semibold text-text-primary">
                {t('pack.modals.create.title')}
              </h3>
              <p className="text-sm text-text-muted">
                {t('pack.modals.create.subtitle')}
              </p>
            </div>
          </div>
          <button
            onClick={handleClose}
            className={clsx(
              "p-2 rounded-lg",
              "hover:bg-slate-mid transition-colors duration-200"
            )}
          >
            <X className="w-5 h-5 text-text-muted" />
          </button>
        </div>

        {/* Content */}
        <div className="flex-1 overflow-y-auto p-6 space-y-6">
          {/* Error message */}
          {error && (
            <div className="p-3 rounded-lg bg-red-500/20 border border-red-500/30 text-red-400 text-sm">
              {error}
            </div>
          )}

          {/* Name field - Required */}
          <div>
            <label className="block text-sm font-medium text-text-primary mb-1.5">
              {t('pack.modals.create.name')} <span className="text-red-400">*</span>
            </label>
            <div className="relative">
              <Package className="absolute left-3 top-1/2 -translate-y-1/2 w-5 h-5 text-text-muted" />
              <input
                type="text"
                value={name}
                onChange={(e) => setName(e.target.value)}
                placeholder={t('pack.modals.create.namePlaceholder')}
                className={clsx(
                  'w-full pl-10 pr-4 py-3 rounded-lg',
                  'bg-slate-dark border border-slate-mid',
                  'text-text-primary placeholder:text-text-muted',
                  'focus:outline-none focus:border-synapse focus:ring-1 focus:ring-synapse/30',
                  'transition-all duration-200'
                )}
              />
            </div>
            <p className="text-xs text-text-muted mt-1">
              {t('pack.modals.create.nameHint')}
            </p>
          </div>

          {/* Pack Type */}
          <div>
            <label className="block text-sm font-medium text-text-primary mb-1.5">
              {t('pack.modals.create.type')}
            </label>
            <div className="grid grid-cols-3 gap-2">
              {PACK_TYPES.map(({ value, labelKey }) => {
                const icon = ASSET_TYPE_ICONS[value] || ASSET_TYPE_ICONS.other
                return (
                  <button
                    key={value}
                    type="button"
                    onClick={() => setPackType(value)}
                    className={clsx(
                      'flex items-center gap-2 px-4 py-3 rounded-lg',
                      'border transition-all duration-200',
                      packType === value
                        ? 'bg-synapse/20 border-synapse text-synapse'
                        : 'bg-slate-dark border-slate-mid text-text-secondary hover:border-slate-light'
                    )}
                  >
                    <span className="text-lg">{icon}</span>
                    <span className="font-medium">{labelKey}</span>
                  </button>
                )
              })}
            </div>
            <p className="text-xs text-text-muted mt-1">
              {t('pack.modals.create.typeHint')}
            </p>
          </div>

          {/* Two column layout for optional fields */}
          <div className="grid grid-cols-2 gap-4">
            {/* Base Model */}
            <div>
              <label className="block text-sm font-medium text-text-primary mb-1.5">
                {t('pack.modals.create.baseModel')}
              </label>
              <div className="relative">
                <Sparkles className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-text-muted" />
                <input
                  type="text"
                  value={baseModel}
                  onChange={(e) => setBaseModel(e.target.value)}
                  placeholder={t('pack.modals.create.baseModelPlaceholder')}
                  className={clsx(
                    'w-full pl-9 pr-4 py-2.5 rounded-lg text-sm',
                    'bg-slate-dark border border-slate-mid',
                    'text-text-primary placeholder:text-text-muted',
                    'focus:outline-none focus:border-synapse',
                    'transition-all duration-200'
                  )}
                />
              </div>
            </div>

            {/* Version */}
            <div>
              <label className="block text-sm font-medium text-text-primary mb-1.5">
                {t('pack.modals.create.version')}
              </label>
              <div className="relative">
                <Hash className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-text-muted" />
                <input
                  type="text"
                  value={version}
                  onChange={(e) => setVersion(e.target.value)}
                  placeholder={t('pack.modals.create.versionPlaceholder')}
                  className={clsx(
                    'w-full pl-9 pr-4 py-2.5 rounded-lg text-sm',
                    'bg-slate-dark border border-slate-mid',
                    'text-text-primary placeholder:text-text-muted',
                    'focus:outline-none focus:border-synapse',
                    'transition-all duration-200'
                  )}
                />
              </div>
            </div>
          </div>

          {/* Author */}
          <div>
            <label className="block text-sm font-medium text-text-primary mb-1.5">
              {t('pack.modals.create.author')}
            </label>
            <div className="relative">
              <User className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-text-muted" />
              <input
                type="text"
                value={author}
                onChange={(e) => setAuthor(e.target.value)}
                placeholder={t('pack.modals.create.authorPlaceholder')}
                className={clsx(
                  'w-full pl-9 pr-4 py-2.5 rounded-lg text-sm',
                  'bg-slate-dark border border-slate-mid',
                  'text-text-primary placeholder:text-text-muted',
                  'focus:outline-none focus:border-synapse',
                  'transition-all duration-200'
                )}
              />
            </div>
          </div>

          {/* Description */}
          <div>
            <label className="block text-sm font-medium text-text-primary mb-1.5">
              {t('pack.modals.create.description')}
            </label>
            <div className="relative">
              <FileText className="absolute left-3 top-3 w-4 h-4 text-text-muted" />
              <textarea
                value={description}
                onChange={(e) => setDescription(e.target.value)}
                placeholder={t('pack.modals.create.descriptionPlaceholder')}
                rows={3}
                className={clsx(
                  'w-full pl-9 pr-4 py-2.5 rounded-lg text-sm resize-none',
                  'bg-slate-dark border border-slate-mid',
                  'text-text-primary placeholder:text-text-muted',
                  'focus:outline-none focus:border-synapse',
                  'transition-all duration-200'
                )}
              />
            </div>
            <p className="text-xs text-text-muted mt-1">
              {t('pack.modals.create.descriptionHint')}
            </p>
          </div>

          {/* Tags */}
          <TagInput
            tags={tags}
            onChange={setTags}
            label={t('pack.modals.create.tags')}
            placeholder={t('pack.modals.create.tagsPlaceholder')}
            hint={t('pack.modals.create.tagsHint')}
          />

          {/* Trigger Words */}
          <TagInput
            tags={triggerWords}
            onChange={setTriggerWords}
            label={t('pack.modals.create.triggerWords')}
            placeholder={t('pack.modals.create.triggerWordsPlaceholder')}
            hint={t('pack.modals.create.triggerWordsHint')}
          />
        </div>

        {/* Footer */}
        <div className="flex justify-end gap-3 p-6 border-t border-slate-mid/50">
          <Button variant="secondary" onClick={handleClose} disabled={isCreating}>
            {t('common.cancel')}
          </Button>
          <Button
            variant="primary"
            onClick={handleCreate}
            disabled={!isValid || isCreating}
          >
            {isCreating ? (
              <>
                <Loader2 className="w-4 h-4 animate-spin" />
                {t('pack.modals.create.creating')}
              </>
            ) : (
              <>
                <Plus className="w-4 h-4" />
                {t('pack.modals.create.title')}
              </>
            )}
          </Button>
        </div>
      </div>
    </div>
  )
}

export default CreatePackModal
