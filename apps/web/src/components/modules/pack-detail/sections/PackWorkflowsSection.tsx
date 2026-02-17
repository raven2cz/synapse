/**
 * PackWorkflowsSection
 *
 * Displays ComfyUI workflows with symlink management.
 *
 * FUNKCE ZACHOVÁNY:
 * - Workflow list with name, filename, description
 * - Symlink status (In ComfyUI / Broken link badges)
 * - is_default badge
 * - Link/Unlink to ComfyUI
 * - Download workflow JSON
 * - Delete workflow
 * - Upload workflow button
 * - Generate Default workflow button
 *
 * VIZUÁLNĚ VYLEPŠENO:
 * - Premium card design
 * - Hover efekty
 * - Lepší status badges
 * - Staggered animace
 */

import { useTranslation } from 'react-i18next'
import { FileJson, Check, AlertTriangle, FolderOpen, X, Download, Trash2, Loader2, Play, Upload } from 'lucide-react'
import { clsx } from 'clsx'
import { Card } from '@/components/ui/Card'
import { Button } from '@/components/ui/Button'
import type { WorkflowInfo } from '../types'
import { ANIMATION_PRESETS } from '../constants'

// =============================================================================
// Types
// =============================================================================

export interface PackWorkflowsSectionProps {
  /**
   * Workflows to display
   */
  workflows: WorkflowInfo[]

  /**
   * Pack name for API calls
   */
  packName: string

  /**
   * Whether base model is needed (disables generate)
   */
  needsBaseModel?: boolean

  /**
   * Handlers
   */
  onCreateSymlink: (filename: string) => void
  onRemoveSymlink: (filename: string) => void
  onDeleteWorkflow: (filename: string) => void
  onGenerateWorkflow: () => void
  onOpenUploadModal: () => void

  /**
   * Loading states
   */
  isCreateSymlinkPending?: boolean
  isRemoveSymlinkPending?: boolean
  isDeletePending?: boolean
  isGeneratePending?: boolean

  /**
   * Animation delay
   */
  animationDelay?: number
}

// =============================================================================
// Sub-components
// =============================================================================

interface WorkflowCardProps {
  workflow: WorkflowInfo
  packName: string
  onCreateSymlink: (filename: string) => void
  onRemoveSymlink: (filename: string) => void
  onDeleteWorkflow: (filename: string) => void
  isCreateSymlinkPending?: boolean
  isRemoveSymlinkPending?: boolean
  isDeletePending?: boolean
}

function WorkflowCard({
  workflow,
  packName,
  onCreateSymlink,
  onRemoveSymlink,
  onDeleteWorkflow,
  isCreateSymlinkPending,
  isRemoveSymlinkPending,
  isDeletePending,
}: WorkflowCardProps) {
  const { t } = useTranslation()
  const hasSymlink = workflow.has_symlink || false
  const symlinkValid = workflow.symlink_valid || false

  return (
    <div
      className={clsx(
        "flex items-center justify-between p-3 rounded-xl border",
        "transition-all duration-200",
        hasSymlink && symlinkValid
          ? "bg-green-500/10 border-green-500/30 hover:border-green-500/50"
          : "bg-slate-dark border-slate-mid/30 hover:border-slate-mid/50",
        "hover:shadow-lg"
      )}
    >
      {/* Left: Workflow Info */}
      <div className="flex items-center gap-3 min-w-0 flex-1">
        <FileJson className={clsx(
          "w-5 h-5 flex-shrink-0",
          hasSymlink && symlinkValid ? "text-green-400" : "text-synapse"
        )} />
        <div className="min-w-0 flex-1">
          <p className="text-text-primary font-medium truncate">{workflow.name}</p>
          <div className="flex items-center gap-2 text-xs text-text-muted flex-wrap">
            <span className="font-mono truncate max-w-[200px]">{workflow.filename}</span>
            {workflow.is_default && (
              <span className="px-1.5 py-0.5 bg-synapse/20 text-synapse rounded text-xs">
                {t('pack.workflows.default')}
              </span>
            )}
            {hasSymlink && symlinkValid && (
              <span className="px-1.5 py-0.5 bg-green-500/20 text-green-400 rounded flex items-center gap-1">
                <Check className="w-3 h-3" />
                {t('pack.workflows.status.linked')}
              </span>
            )}
            {hasSymlink && !symlinkValid && (
              <span className="px-1.5 py-0.5 bg-orange-500/20 text-orange-400 rounded flex items-center gap-1">
                <AlertTriangle className="w-3 h-3" />
                {t('pack.workflows.status.broken')}
              </span>
            )}
          </div>
          {/* Local path */}
          {workflow.local_path && (
            <p className="text-xs text-text-muted mt-1 font-mono truncate" title={workflow.local_path}>
              {workflow.local_path}
            </p>
          )}
          {workflow.description && (
            <p className="text-xs text-text-muted mt-1 line-clamp-2">{workflow.description}</p>
          )}
        </div>
      </div>

      {/* Right: Actions */}
      <div className="flex items-center gap-2 flex-shrink-0 ml-3">
        {/* Link/Unlink to ComfyUI */}
        {hasSymlink ? (
          <button
            onClick={() => {
              if (confirm(t('pack.workflows.confirmUnlink'))) {
                onRemoveSymlink(workflow.filename)
              }
            }}
            disabled={isRemoveSymlinkPending}
            className={clsx(
              "px-3 py-1.5 rounded-lg text-sm",
              "bg-slate-mid/50 text-text-secondary",
              "hover:bg-slate-mid transition-all duration-200",
              "flex items-center gap-1.5"
            )}
            title={t('pack.workflows.unlink')}
          >
            {isRemoveSymlinkPending ? (
              <Loader2 className="w-4 h-4 animate-spin" />
            ) : (
              <X className="w-4 h-4" />
            )}
            {t('pack.workflows.unlink')}
          </button>
        ) : (
          <button
            onClick={() => onCreateSymlink(workflow.filename)}
            disabled={isCreateSymlinkPending}
            className={clsx(
              "px-3 py-1.5 rounded-lg text-sm",
              "bg-synapse/20 text-synapse",
              "hover:bg-synapse/30 transition-all duration-200",
              "flex items-center gap-1.5"
            )}
            title={t('pack.workflows.link')}
          >
            {isCreateSymlinkPending ? (
              <Loader2 className="w-4 h-4 animate-spin" />
            ) : (
              <FolderOpen className="w-4 h-4" />
            )}
            {t('pack.workflows.link')}
          </button>
        )}

        {/* Download workflow JSON */}
        <button
          onClick={() => {
            window.open(`/api/packs/${encodeURIComponent(packName)}/workflow/${encodeURIComponent(workflow.filename)}`, '_blank')
          }}
          className={clsx(
            "p-1.5 rounded-lg",
            "bg-slate-mid/50 text-text-secondary",
            "hover:bg-slate-mid hover:text-synapse",
            "transition-all duration-200"
          )}
          title={t('pack.workflows.downloadJson')}
        >
          <Download className="w-4 h-4" />
        </button>

        {/* Delete workflow */}
        <button
          onClick={() => {
            if (confirm(t('pack.workflows.confirmDelete', { name: workflow.name }))) {
              onDeleteWorkflow(workflow.filename)
            }
          }}
          disabled={isDeletePending}
          className={clsx(
            "p-1.5 rounded-lg",
            "bg-red-500/20 text-red-400",
            "hover:bg-red-500/30",
            "transition-all duration-200"
          )}
          title={t('pack.workflows.deleteWorkflow')}
        >
          {isDeletePending ? (
            <Loader2 className="w-4 h-4 animate-spin" />
          ) : (
            <Trash2 className="w-4 h-4" />
          )}
        </button>
      </div>
    </div>
  )
}

// =============================================================================
// Main Component
// =============================================================================

export function PackWorkflowsSection({
  workflows,
  packName,
  needsBaseModel = false,
  onCreateSymlink,
  onRemoveSymlink,
  onDeleteWorkflow,
  onGenerateWorkflow,
  onOpenUploadModal,
  isCreateSymlinkPending,
  isRemoveSymlinkPending,
  isDeletePending,
  isGeneratePending,
  animationDelay = 0,
}: PackWorkflowsSectionProps) {
  const { t } = useTranslation()

  return (
    <div
      className={ANIMATION_PRESETS.sectionEnter}
      style={{ animationDelay: `${animationDelay}ms`, animationFillMode: 'both' }}
    >
      <Card className="p-4">
        {/* Header */}
      <div className="flex items-center justify-between mb-3">
        <h3 className="text-sm font-semibold text-text-primary flex items-center gap-2">
          <FileJson className="w-4 h-4 text-synapse" />
          {t('pack.workflows.comfyuiWorkflows')}
          <span className="text-text-muted font-normal">({workflows?.length || 0})</span>
        </h3>

        <div className="flex items-center gap-2">
          {/* Upload button */}
          <Button
            size="sm"
            variant="secondary"
            onClick={onOpenUploadModal}
            className="transition-all duration-200 hover:scale-105"
          >
            <Upload className="w-4 h-4" />
            {t('pack.workflows.upload')}
          </Button>

          {/* Generate Default button */}
          <div className="relative group">
            <Button
              size="sm"
              variant="primary"
              disabled={needsBaseModel || isGeneratePending}
              onClick={onGenerateWorkflow}
              className={clsx(
                "transition-all duration-200",
                !needsBaseModel && !isGeneratePending && "hover:scale-105",
                needsBaseModel && "opacity-50 cursor-not-allowed"
              )}
            >
              {isGeneratePending ? (
                <Loader2 className="w-4 h-4 animate-spin" />
              ) : (
                <Play className="w-4 h-4" />
              )}
              {t('pack.workflows.generate')}
            </Button>
            {needsBaseModel && (
              <div className={clsx(
                "absolute bottom-full left-1/2 -translate-x-1/2 mb-2",
                "px-3 py-2 rounded-lg",
                "bg-slate-dark border border-amber-500/50",
                "text-xs text-amber-400 whitespace-nowrap",
                "opacity-0 group-hover:opacity-100",
                "transition-opacity pointer-events-none",
                "z-10"
              )}>
                {t('pack.workflows.resolveFirst')}
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Workflows List */}
      {workflows?.length > 0 ? (
        <div className="space-y-2">
          {workflows.map((workflow, idx) => (
            <WorkflowCard
              key={idx}
              workflow={workflow}
              packName={packName}
              onCreateSymlink={onCreateSymlink}
              onRemoveSymlink={onRemoveSymlink}
              onDeleteWorkflow={onDeleteWorkflow}
              isCreateSymlinkPending={isCreateSymlinkPending}
              isRemoveSymlinkPending={isRemoveSymlinkPending}
              isDeletePending={isDeletePending}
            />
          ))}
        </div>
      ) : (
        <div className="text-center py-8 text-text-muted">
          <FileJson className="w-12 h-12 mx-auto mb-3 opacity-50" />
          <p className="text-sm">{t('pack.workflows.noWorkflows')}</p>
          <p className="text-xs mt-1">
            {t('pack.workflows.emptyHint')}
          </p>
        </div>
      )}
      </Card>
    </div>
  )
}

export default PackWorkflowsSection
