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
                default
              </span>
            )}
            {hasSymlink && symlinkValid && (
              <span className="px-1.5 py-0.5 bg-green-500/20 text-green-400 rounded flex items-center gap-1">
                <Check className="w-3 h-3" />
                In ComfyUI
              </span>
            )}
            {hasSymlink && !symlinkValid && (
              <span className="px-1.5 py-0.5 bg-orange-500/20 text-orange-400 rounded flex items-center gap-1">
                <AlertTriangle className="w-3 h-3" />
                Broken link
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
              if (confirm('Remove workflow from ComfyUI?')) {
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
            title="Remove from ComfyUI"
          >
            {isRemoveSymlinkPending ? (
              <Loader2 className="w-4 h-4 animate-spin" />
            ) : (
              <X className="w-4 h-4" />
            )}
            Unlink
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
            title="Add to ComfyUI workflows"
          >
            {isCreateSymlinkPending ? (
              <Loader2 className="w-4 h-4 animate-spin" />
            ) : (
              <FolderOpen className="w-4 h-4" />
            )}
            Link to ComfyUI
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
          title="Download workflow JSON"
        >
          <Download className="w-4 h-4" />
        </button>

        {/* Delete workflow */}
        <button
          onClick={() => {
            if (confirm(`Delete workflow "${workflow.name}"?`)) {
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
          title="Delete workflow"
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
          ComfyUI Workflows
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
            Upload
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
              Generate Default
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
                ⚠️ Resolve all models before generating workflow
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
          <p className="text-sm">No workflows yet</p>
          <p className="text-xs mt-1">
            Click "Generate Default" to create one based on pack configuration,
            <br />or "Upload" to add an existing workflow.
          </p>
        </div>
      )}
      </Card>
    </div>
  )
}

export default PackWorkflowsSection
