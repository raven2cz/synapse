/**
 * UpdateOptionsDialog - Options dialog shown before applying an update.
 *
 * Allows user to choose what to update:
 * - Model files (always, required)
 * - Merge new previews from Civitai
 * - Update description from Civitai
 * - Sync model info (trigger words, base model)
 */

import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { createPortal } from 'react-dom'
import {
  X,
  Download,
  Image,
  FileText,
  Info,
  Loader2,
  CheckSquare,
  Square,
  Lock,
} from 'lucide-react'
import { clsx } from 'clsx'
import { Button } from '@/components/ui/Button'

export interface UpdateOptionsResult {
  merge_previews: boolean
  update_description: boolean
  update_model_info: boolean
}

interface UpdateOptionsDialogProps {
  open: boolean
  onClose: () => void
  onApply: (options: UpdateOptionsResult) => void
  packName: string
  changesCount: number
  isApplying: boolean
}

export function UpdateOptionsDialog({
  open,
  onClose,
  onApply,
  packName,
  changesCount,
  isApplying,
}: UpdateOptionsDialogProps) {
  const { t } = useTranslation()
  const [mergePreviews, setMergePreviews] = useState(false)
  const [updateDescription, setUpdateDescription] = useState(false)
  const [updateModelInfo, setUpdateModelInfo] = useState(false)

  if (!open) return null

  const handleApply = () => {
    onApply({
      merge_previews: mergePreviews,
      update_description: updateDescription,
      update_model_info: updateModelInfo,
    })
  }

  const dialog = (
    <div className="fixed inset-0 z-[100] flex items-center justify-center">
      <div
        className="absolute inset-0 bg-black/80 backdrop-blur-sm"
        onClick={!isApplying ? onClose : undefined}
      />
      <div className="relative w-full max-w-md m-4 bg-slate-900 rounded-2xl border border-slate-mid/50 shadow-2xl">
        {/* Header */}
        <div className="flex items-center justify-between p-5 border-b border-slate-mid/30">
          <div>
            <h2 className="font-semibold text-text-primary">{t('updates.options.title')}</h2>
            <p className="text-sm text-text-muted mt-0.5">{packName}</p>
          </div>
          <button
            onClick={onClose}
            disabled={isApplying}
            className="p-2 rounded-lg hover:bg-slate-mid text-text-muted transition-colors disabled:opacity-50"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Options */}
        <div className="p-5 space-y-4">
          {/* Model files - always required */}
          <div className="flex items-start gap-3 p-3 bg-synapse/5 border border-synapse/20 rounded-xl">
            <div className="p-1.5 bg-synapse/20 rounded-lg mt-0.5">
              <Lock className="w-4 h-4 text-synapse" />
            </div>
            <div className="flex-1">
              <div className="flex items-center gap-2">
                <span className="font-medium text-text-primary text-sm">{t('updates.options.modelFiles')}</span>
                <span className="text-[10px] px-1.5 py-0.5 bg-synapse/20 text-synapse rounded font-medium">
                  {t('updates.options.required')}
                </span>
              </div>
              <p className="text-xs text-text-muted mt-0.5">
                {t('updates.options.modelFilesDesc', { count: changesCount })}
              </p>
            </div>
          </div>

          {/* Merge previews */}
          <button
            onClick={() => setMergePreviews(!mergePreviews)}
            className={clsx(
              'w-full flex items-start gap-3 p-3 rounded-xl border transition-colors text-left',
              mergePreviews
                ? 'bg-purple-500/5 border-purple-500/20'
                : 'bg-slate-dark/50 border-slate-mid/20 hover:border-slate-mid/40'
            )}
          >
            <div className="mt-0.5">
              {mergePreviews ? (
                <CheckSquare className="w-5 h-5 text-purple-400" />
              ) : (
                <Square className="w-5 h-5 text-text-muted" />
              )}
            </div>
            <div className="flex-1">
              <div className="flex items-center gap-2">
                <Image className="w-4 h-4 text-text-muted" />
                <span className="font-medium text-text-primary text-sm">{t('updates.options.mergePreviews')}</span>
              </div>
              <p className="text-xs text-text-muted mt-0.5">{t('updates.options.mergePreviewsDesc')}</p>
            </div>
          </button>

          {/* Update description */}
          <button
            onClick={() => setUpdateDescription(!updateDescription)}
            className={clsx(
              'w-full flex items-start gap-3 p-3 rounded-xl border transition-colors text-left',
              updateDescription
                ? 'bg-blue-500/5 border-blue-500/20'
                : 'bg-slate-dark/50 border-slate-mid/20 hover:border-slate-mid/40'
            )}
          >
            <div className="mt-0.5">
              {updateDescription ? (
                <CheckSquare className="w-5 h-5 text-blue-400" />
              ) : (
                <Square className="w-5 h-5 text-text-muted" />
              )}
            </div>
            <div className="flex-1">
              <div className="flex items-center gap-2">
                <FileText className="w-4 h-4 text-text-muted" />
                <span className="font-medium text-text-primary text-sm">{t('updates.options.updateDescription')}</span>
              </div>
              <p className="text-xs text-text-muted mt-0.5">{t('updates.options.updateDescriptionDesc')}</p>
            </div>
          </button>

          {/* Update model info */}
          <button
            onClick={() => setUpdateModelInfo(!updateModelInfo)}
            className={clsx(
              'w-full flex items-start gap-3 p-3 rounded-xl border transition-colors text-left',
              updateModelInfo
                ? 'bg-green-500/5 border-green-500/20'
                : 'bg-slate-dark/50 border-slate-mid/20 hover:border-slate-mid/40'
            )}
          >
            <div className="mt-0.5">
              {updateModelInfo ? (
                <CheckSquare className="w-5 h-5 text-green-400" />
              ) : (
                <Square className="w-5 h-5 text-text-muted" />
              )}
            </div>
            <div className="flex-1">
              <div className="flex items-center gap-2">
                <Info className="w-4 h-4 text-text-muted" />
                <span className="font-medium text-text-primary text-sm">{t('updates.options.updateModelInfo')}</span>
              </div>
              <p className="text-xs text-text-muted mt-0.5">{t('updates.options.updateModelInfoDesc')}</p>
            </div>
          </button>
        </div>

        {/* Footer */}
        <div className="flex items-center justify-end gap-3 p-5 border-t border-slate-mid/30">
          <Button variant="secondary" onClick={onClose} disabled={isApplying}>
            {t('common.cancel')}
          </Button>
          <Button variant="primary" onClick={handleApply} disabled={isApplying}>
            {isApplying ? (
              <Loader2 className="w-4 h-4 animate-spin" />
            ) : (
              <Download className="w-4 h-4" />
            )}
            {t('updates.options.apply')}
          </Button>
        </div>
      </div>
    </div>
  )

  return createPortal(dialog, document.body)
}
