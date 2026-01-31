/**
 * PackParametersSection
 *
 * Displays generation parameters in a responsive grid.
 *
 * FUNKCE ZACHOVÁNY:
 * - All parameter types: clip_skip, strength, cfg_scale, steps, sampler, scheduler, resolution, denoise
 * - Edit button to open parameters modal
 * - Empty state message
 *
 * VIZUÁLNĚ VYLEPŠENO:
 * - Premium parameter cards
 * - Hover effects
 * - Better typography
 * - Staggered animations
 */

import { Info, Edit3, Sliders } from 'lucide-react'
import { clsx } from 'clsx'
import { Card } from '@/components/ui/Card'
import type { ParametersInfo, ModelInfoResponse } from '../types'
import { ANIMATION_PRESETS } from '../constants'

// =============================================================================
// Types
// =============================================================================

export interface PackParametersSectionProps {
  /**
   * Generation parameters
   */
  parameters?: ParametersInfo

  /**
   * Model info (for strength_recommended)
   */
  modelInfo?: ModelInfoResponse

  /**
   * Handler for edit button
   */
  onEdit: () => void

  /**
   * Animation delay
   */
  animationDelay?: number
}

// =============================================================================
// Sub-components
// =============================================================================

interface ParameterCardProps {
  label: string
  value: string | number
  highlight?: boolean
  large?: boolean
}

function ParameterCard({ label, value, highlight = false, large = true }: ParameterCardProps) {
  return (
    <div className={clsx(
      "bg-slate-dark rounded-xl p-3 text-center",
      "transition-all duration-200",
      "hover:bg-slate-dark/80 hover:scale-105",
      "border border-transparent hover:border-slate-mid/50",
      large ? "min-w-[100px]" : "min-w-[120px]"
    )}>
      <span className="text-text-muted block text-xs mb-1">{label}</span>
      <span className={clsx(
        large ? "font-bold text-xl" : "font-medium",
        highlight ? "text-synapse" : "text-text-primary"
      )}>
        {value}
      </span>
    </div>
  )
}

// =============================================================================
// Main Component
// =============================================================================

export function PackParametersSection({
  parameters,
  modelInfo,
  onEdit,
  animationDelay = 0,
}: PackParametersSectionProps) {
  // Check if any parameters exist
  const hasParameters = !!(
    parameters?.clip_skip != null ||
    modelInfo?.strength_recommended != null ||
    parameters?.cfg_scale != null ||
    parameters?.steps != null ||
    parameters?.sampler ||
    parameters?.scheduler ||
    (parameters?.width != null && parameters?.height != null) ||
    parameters?.denoise != null
  )

  return (
    <div
      className={ANIMATION_PRESETS.sectionEnter}
      style={{ animationDelay: `${animationDelay}ms`, animationFillMode: 'both' }}
    >
      <Card className="p-4">
        {/* Header */}
      <div className="flex items-center justify-between mb-3">
        <h3 className="text-sm font-semibold text-synapse flex items-center gap-2">
          <Sliders className="w-4 h-4" />
          Generation Settings
        </h3>
        <button
          onClick={onEdit}
          className={clsx(
            "text-xs text-synapse flex items-center gap-1",
            "hover:text-synapse/80 transition-colors duration-200"
          )}
        >
          <Edit3 className="w-3 h-3" />
          Edit
        </button>
      </div>

      {/* Parameters Grid */}
      {hasParameters ? (
        <div className="flex flex-wrap gap-3">
          {/* Clip Skip - highlighted */}
          {parameters?.clip_skip != null && (
            <ParameterCard
              label="Clip Skip"
              value={parameters.clip_skip}
              highlight={true}
            />
          )}

          {/* Strength (from model_info) - highlighted */}
          {modelInfo?.strength_recommended != null && (
            <ParameterCard
              label="Strength"
              value={modelInfo.strength_recommended}
              highlight={true}
            />
          )}

          {/* CFG Scale */}
          {parameters?.cfg_scale != null && (
            <ParameterCard
              label="CFG Scale"
              value={parameters.cfg_scale}
            />
          )}

          {/* Steps */}
          {parameters?.steps != null && (
            <ParameterCard
              label="Steps"
              value={parameters.steps}
            />
          )}

          {/* Sampler */}
          {parameters?.sampler && (
            <ParameterCard
              label="Sampler"
              value={parameters.sampler}
              large={false}
            />
          )}

          {/* Scheduler */}
          {parameters?.scheduler && (
            <ParameterCard
              label="Scheduler"
              value={parameters.scheduler}
              large={false}
            />
          )}

          {/* Resolution */}
          {parameters?.width != null && parameters?.height != null && (
            <ParameterCard
              label="Resolution"
              value={`${parameters.width}×${parameters.height}`}
              large={false}
            />
          )}

          {/* Denoise */}
          {parameters?.denoise != null && (
            <ParameterCard
              label="Denoise"
              value={parameters.denoise}
            />
          )}
        </div>
      ) : (
        <div className="text-center py-6">
          <Info className="w-8 h-8 mx-auto mb-2 text-text-muted/50" />
          <p className="text-text-muted text-sm">
            No generation parameters set. Click Edit to add some.
          </p>
        </div>
      )}
      </Card>
    </div>
  )
}

export default PackParametersSection
