/**
 * PackParametersSection
 *
 * Displays generation parameters in a responsive grid with comprehensive category support.
 *
 * FEATURES:
 * - Dynamic display of ALL parameters (not hardcoded list)
 * - Categorized: Generation, Resolution, HiRes, Model, ControlNet, etc.
 * - Collapsible sections for advanced categories
 * - Edit button to open parameters modal
 * - Empty state message
 * - Premium styling with hover effects
 */

import { useState, useMemo, useCallback } from 'react'
import {
  Info, Edit3, Sliders, Maximize2, Sparkles, Settings2, ChevronDown, ChevronRight,
  Layers, Zap, Paintbrush, Grid3X3, Cpu, Box, Image, ImageIcon, FileText, Calculator, Pencil,
} from 'lucide-react'
import { clsx } from 'clsx'
import { Card } from '@/components/ui/Card'
import type { ParametersInfo, ModelInfoResponse, PreviewInfo, ParameterSource, ParameterSourceType } from '../types'
import { ANIMATION_PRESETS } from '../constants'
import { extractApplicableParams, hasExtractableParams, aggregateFromPreviews } from '@/lib/parameters'

// =============================================================================
// Types
// =============================================================================

export interface PackParametersSectionProps {
  parameters?: ParametersInfo
  modelInfo?: ModelInfoResponse
  onEdit: () => void
  animationDelay?: number
  /** Previews with metadata for source selection */
  previews?: PreviewInfo[]
  /** Current parameter source */
  currentSource?: ParameterSource
  /** Callback when parameters are applied from a source */
  onApplyFromSource?: (params: Record<string, unknown>, source: ParameterSource) => void
}

type CategoryKey = 'generation' | 'resolution' | 'hires' | 'model' | 'controlnet' | 'inpainting' | 'batch' | 'advanced' | 'sdxl' | 'freeu' | 'ipadapter' | 'custom'

// =============================================================================
// Constants - Mirroring EditParametersModal
// =============================================================================

const PARAM_CATEGORIES: Record<CategoryKey, string[]> = {
  generation: ['sampler', 'scheduler', 'steps', 'cfg_scale', 'clip_skip', 'denoise', 'seed', 'strength', 'eta', 'strength_recommended'],
  resolution: ['width', 'height', 'aspect_ratio'],
  hires: ['hires_fix', 'hires_upscaler', 'hires_steps', 'hires_denoise', 'hires_scale', 'hires_width', 'hires_height'],
  model: ['vae', 'base_model', 'model_hash'],
  controlnet: ['controlnet_enabled', 'controlnet_strength', 'controlnet_start', 'controlnet_end', 'controlnet_model', 'control_mode'],
  inpainting: ['inpaint_full_res', 'inpaint_full_res_padding', 'mask_blur', 'inpainting_fill'],
  batch: ['batch_size', 'batch_count', 'n_iter'],
  advanced: ['s_noise', 's_churn', 's_tmin', 's_tmax', 'noise_offset', 'tiling', 'ensd'],
  sdxl: ['refiner_checkpoint', 'refiner_switch', 'aesthetic_score', 'negative_aesthetic_score'],
  freeu: ['freeu_enabled', 'freeu_b1', 'freeu_b2', 'freeu_s1', 'freeu_s2'],
  ipadapter: ['ip_adapter_enabled', 'ip_adapter_weight', 'ip_adapter_noise', 'ip_adapter_model'],
  custom: [],
}

const PARAM_LABELS: Record<string, string> = {
  sampler: 'Sampler',
  scheduler: 'Scheduler',
  steps: 'Steps',
  cfg_scale: 'CFG Scale',
  clip_skip: 'Clip Skip',
  denoise: 'Denoise',
  seed: 'Seed',
  strength: 'LoRA Strength',
  strength_recommended: 'Recommended Strength',
  eta: 'Eta',
  width: 'Width',
  height: 'Height',
  aspect_ratio: 'Aspect Ratio',
  hires_fix: 'HiRes Fix',
  hires_upscaler: 'Upscaler',
  hires_steps: 'HiRes Steps',
  hires_denoise: 'HiRes Denoise',
  hires_scale: 'HiRes Scale',
  hires_width: 'HiRes Width',
  hires_height: 'HiRes Height',
  vae: 'VAE',
  base_model: 'Base Model',
  model_hash: 'Model Hash',
  controlnet_enabled: 'ControlNet',
  controlnet_strength: 'CN Strength',
  controlnet_start: 'CN Start',
  controlnet_end: 'CN End',
  controlnet_model: 'CN Model',
  control_mode: 'Control Mode',
  inpaint_full_res: 'Full Res',
  inpaint_full_res_padding: 'Padding',
  mask_blur: 'Mask Blur',
  inpainting_fill: 'Fill',
  batch_size: 'Batch Size',
  batch_count: 'Batch Count',
  n_iter: 'Iterations',
  s_noise: 'Sigma Noise',
  s_churn: 'Sigma Churn',
  s_tmin: 'Sigma Tmin',
  s_tmax: 'Sigma Tmax',
  noise_offset: 'Noise Offset',
  tiling: 'Tiling',
  ensd: 'ENSD',
  refiner_checkpoint: 'Refiner',
  refiner_switch: 'Refiner Switch',
  aesthetic_score: 'Aesthetic Score',
  negative_aesthetic_score: 'Neg Aesthetic',
  freeu_enabled: 'FreeU',
  freeu_b1: 'FreeU B1',
  freeu_b2: 'FreeU B2',
  freeu_s1: 'FreeU S1',
  freeu_s2: 'FreeU S2',
  ip_adapter_enabled: 'IP-Adapter',
  ip_adapter_weight: 'IP Weight',
  ip_adapter_noise: 'IP Noise',
  ip_adapter_model: 'IP Model',
}

const CATEGORY_META: Record<CategoryKey, { label: string; icon: React.ElementType; color: string }> = {
  generation: { label: 'Generation', icon: Sliders, color: 'text-synapse' },
  resolution: { label: 'Resolution', icon: Maximize2, color: 'text-blue-400' },
  hires: { label: 'HiRes Fix', icon: Sparkles, color: 'text-amber-400' },
  model: { label: 'Model', icon: Layers, color: 'text-green-400' },
  controlnet: { label: 'ControlNet', icon: Zap, color: 'text-cyan-400' },
  inpainting: { label: 'Inpainting', icon: Paintbrush, color: 'text-pink-400' },
  batch: { label: 'Batch', icon: Grid3X3, color: 'text-orange-400' },
  advanced: { label: 'Advanced', icon: Cpu, color: 'text-red-400' },
  sdxl: { label: 'SDXL', icon: Box, color: 'text-violet-400' },
  freeu: { label: 'FreeU', icon: Image, color: 'text-teal-400' },
  ipadapter: { label: 'IP-Adapter', icon: Image, color: 'text-indigo-400' },
  custom: { label: 'Custom', icon: Settings2, color: 'text-purple-400' },
}

const HIGHLIGHT_PARAMS = new Set(['clip_skip', 'strength', 'strength_recommended'])

// =============================================================================
// Utility Functions
// =============================================================================

function getParamLabel(key: string): string {
  return PARAM_LABELS[key] || key.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase())
}

function formatParamValue(_key: string, value: unknown): string {
  if (value === null || value === undefined) return ''
  if (typeof value === 'boolean') return value ? 'Enabled' : 'Disabled'
  if (typeof value === 'number') {
    if (Number.isInteger(value)) return value.toString()
    return value.toFixed(2).replace(/\.?0+$/, '')
  }
  return String(value)
}

function getParamCategory(key: string): CategoryKey {
  for (const [category, keys] of Object.entries(PARAM_CATEGORIES)) {
    if (keys.includes(key)) return category as CategoryKey
  }
  return 'custom'
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
      large ? "min-w-[100px]" : "min-w-[110px]"
    )}>
      <span className="text-text-muted block text-xs mb-1">{label}</span>
      <span className={clsx(
        large ? "font-bold text-xl" : "font-medium text-sm",
        highlight ? "text-synapse" : "text-text-primary"
      )}>
        {value}
      </span>
    </div>
  )
}

interface CategoryGroupProps {
  category: CategoryKey
  params: Array<{ key: string; value: string; highlight: boolean }>
  collapsible?: boolean
  defaultExpanded?: boolean
}

// =============================================================================
// Source Picker Component
// =============================================================================

interface SourcePickerProps {
  currentSource?: ParameterSource
  previews?: PreviewInfo[]
  onSelectSource: (source: ParameterSource) => void
}

function SourcePicker({ currentSource, previews = [], onSelectSource }: SourcePickerProps) {
  const [isOpen, setIsOpen] = useState(false)

  // Find previews with extractable meta
  const previewsWithMeta = useMemo(() => {
    return previews
      .map((p, i) => ({ preview: p, index: i }))
      .filter(({ preview }) => preview.meta && hasExtractableParams(preview.meta as Record<string, unknown>))
  }, [previews])

  // Check if aggregation is possible (2+ previews with meta)
  const canAggregate = previewsWithMeta.length >= 2

  // Get label for current source
  const getSourceLabel = (source?: ParameterSource): string => {
    if (!source) return 'Manual'
    switch (source.type) {
      case 'manual': return 'Manual'
      case 'description': return 'From Description'
      case 'image': return `Image #${(source.imageIndex ?? 0) + 1}`
      case 'aggregated': return 'Aggregated'
      default: return 'Manual'
    }
  }

  // Get icon for source type
  const getSourceIcon = (type: ParameterSourceType) => {
    switch (type) {
      case 'manual': return Pencil
      case 'description': return FileText
      case 'image': return ImageIcon
      case 'aggregated': return Calculator
      default: return Pencil
    }
  }

  const CurrentIcon = getSourceIcon(currentSource?.type ?? 'manual')

  // No sources available - don't show picker
  if (previewsWithMeta.length === 0) {
    return null
  }

  return (
    <div className="relative">
      <button
        onClick={() => setIsOpen(!isOpen)}
        className={clsx(
          "flex items-center gap-1.5 px-2 py-1 rounded-md text-xs",
          "bg-slate-dark/50 hover:bg-slate-dark",
          "text-text-muted hover:text-text-primary",
          "border border-slate-mid/30 hover:border-slate-mid/50",
          "transition-all duration-200"
        )}
      >
        <CurrentIcon className="w-3 h-3" />
        <span>{getSourceLabel(currentSource)}</span>
        <ChevronDown className={clsx("w-3 h-3 transition-transform", isOpen && "rotate-180")} />
      </button>

      {isOpen && (
        <>
          {/* Backdrop */}
          <div
            className="fixed inset-0 z-40"
            onClick={() => setIsOpen(false)}
          />

          {/* Dropdown */}
          <div className={clsx(
            "absolute right-0 top-full mt-1 z-50",
            "min-w-[180px] py-1",
            "bg-slate-dark border border-slate-mid/50 rounded-lg shadow-xl",
            "animate-in fade-in slide-in-from-top-1 duration-150"
          )}>
            {/* Manual option */}
            <button
              onClick={() => {
                onSelectSource({ type: 'manual' })
                setIsOpen(false)
              }}
              className={clsx(
                "w-full flex items-center gap-2 px-3 py-2 text-xs text-left",
                "hover:bg-slate-mid/30 transition-colors",
                currentSource?.type === 'manual' && "bg-synapse/10 text-synapse"
              )}
            >
              <Pencil className="w-3 h-3" />
              Manual
            </button>

            {/* Divider */}
            {previewsWithMeta.length > 0 && (
              <div className="h-px bg-slate-mid/30 my-1" />
            )}

            {/* Image sources */}
            {previewsWithMeta.map(({ preview, index }) => (
              <button
                key={index}
                onClick={() => {
                  onSelectSource({
                    type: 'image',
                    imageIndex: index,
                    imageUrl: preview.thumbnail_url || preview.url,
                  })
                  setIsOpen(false)
                }}
                className={clsx(
                  "w-full flex items-center gap-2 px-3 py-2 text-xs text-left",
                  "hover:bg-slate-mid/30 transition-colors",
                  currentSource?.type === 'image' && currentSource.imageIndex === index && "bg-synapse/10 text-synapse"
                )}
              >
                <ImageIcon className="w-3 h-3" />
                Image #{index + 1}
                {preview.thumbnail_url && (
                  <img
                    src={preview.thumbnail_url}
                    alt=""
                    className="w-6 h-6 rounded object-cover ml-auto"
                  />
                )}
              </button>
            ))}

            {/* Aggregated option */}
            {canAggregate && (
              <>
                <div className="h-px bg-slate-mid/30 my-1" />
                <button
                  onClick={() => {
                    onSelectSource({ type: 'aggregated' })
                    setIsOpen(false)
                  }}
                  className={clsx(
                    "w-full flex items-center gap-2 px-3 py-2 text-xs text-left",
                    "hover:bg-slate-mid/30 transition-colors",
                    currentSource?.type === 'aggregated' && "bg-synapse/10 text-synapse"
                  )}
                >
                  <Calculator className="w-3 h-3" />
                  Aggregated
                  <span className="text-text-muted ml-auto">
                    ({previewsWithMeta.length} images)
                  </span>
                </button>
              </>
            )}
          </div>
        </>
      )}
    </div>
  )
}

// =============================================================================
// Category Group Component
// =============================================================================

function CategoryGroup({
  category,
  params,
  collapsible = false,
  defaultExpanded = true
}: CategoryGroupProps) {
  const [isExpanded, setIsExpanded] = useState(defaultExpanded)
  const meta = CATEGORY_META[category]
  const Icon = meta.icon

  if (params.length === 0) return null

  return (
    <div>
      {collapsible ? (
        <button
          onClick={() => setIsExpanded(!isExpanded)}
          className={clsx(
            "flex items-center gap-1.5 mb-2",
            "text-xs text-text-muted hover:text-text-primary",
            "transition-colors duration-200"
          )}
        >
          {isExpanded ? (
            <ChevronDown className="w-3 h-3" />
          ) : (
            <ChevronRight className="w-3 h-3" />
          )}
          <Icon className={clsx("w-3 h-3", meta.color)} />
          <span>{meta.label}</span>
          <span className="text-text-muted/60">({params.length})</span>
        </button>
      ) : (
        <div className="flex items-center gap-1.5 mb-2">
          <Icon className={clsx("w-3 h-3", meta.color)} />
          <span className="text-xs text-text-muted">{meta.label}</span>
        </div>
      )}

      {(!collapsible || isExpanded) && (
        <div className="flex flex-wrap gap-2 justify-start">
          {params.map(({ key, value, highlight }) => (
            <ParameterCard
              key={key}
              label={getParamLabel(key)}
              value={value}
              highlight={highlight}
              large={!['sampler', 'scheduler', 'hires_upscaler', 'vae', 'base_model'].includes(key)}
            />
          ))}
        </div>
      )}
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
  previews = [],
  currentSource,
  onApplyFromSource,
}: PackParametersSectionProps) {
  // Handle source selection - extract params and call callback
  const handleSourceSelect = useCallback((source: ParameterSource) => {
    if (!onApplyFromSource) return

    if (source.type === 'manual') {
      // Manual - no automatic application, just track source
      onApplyFromSource({}, source)
    } else if (source.type === 'image' && source.imageIndex !== undefined) {
      // Extract from specific image
      const preview = previews[source.imageIndex]
      if (preview?.meta) {
        const params = extractApplicableParams(preview.meta as Record<string, unknown>)
        onApplyFromSource(params, source)
      }
    } else if (source.type === 'aggregated') {
      // Aggregate from all previews with meta
      const previewsForAggregation = previews
        .filter(p => p.meta && hasExtractableParams(p.meta as Record<string, unknown>))
        .map(p => ({ meta: p.meta as Record<string, unknown> }))

      const result = aggregateFromPreviews(previewsForAggregation)
      onApplyFromSource(result.parameters, { ...source, confidence: result.overallConfidence })
    }
  }, [previews, onApplyFromSource])
  // Collect and categorize all parameters
  const categorizedParams = useMemo(() => {
    const result: Record<CategoryKey, Array<{ key: string; value: string; highlight: boolean }>> = {
      generation: [],
      resolution: [],
      hires: [],
      model: [],
      controlnet: [],
      inpainting: [],
      batch: [],
      advanced: [],
      sdxl: [],
      freeu: [],
      ipadapter: [],
      custom: [],
    }

    // Add strength_recommended from modelInfo if present
    if (modelInfo?.strength_recommended != null) {
      result.generation.push({
        key: 'strength_recommended',
        value: formatParamValue('strength_recommended', modelInfo.strength_recommended),
        highlight: true,
      })
    }

    // Process all parameters
    if (parameters) {
      // Special handling for resolution - combine width & height
      const hasResolution = parameters.width != null && parameters.height != null

      for (const [key, value] of Object.entries(parameters)) {
        if (value === null || value === undefined) continue

        // Skip width/height individually if we're showing combined resolution
        if (hasResolution && (key === 'width' || key === 'height')) continue

        const category = getParamCategory(key)
        const formatted = formatParamValue(key, value)

        if (formatted) {
          result[category].push({
            key,
            value: formatted,
            highlight: HIGHLIGHT_PARAMS.has(key),
          })
        }
      }

      // Add combined resolution
      if (hasResolution) {
        result.resolution.push({
          key: 'resolution',
          value: `${parameters.width}×${parameters.height}`,
          highlight: false,
        })
      }
    }

    return result
  }, [parameters, modelInfo])

  // Check if any parameters exist
  const hasParameters = Object.values(categorizedParams).some(arr => arr.length > 0)

  // Categories to show in order
  const categoryOrder: CategoryKey[] = [
    'generation', 'resolution', 'hires', 'model', 'controlnet',
    'inpainting', 'batch', 'advanced', 'sdxl', 'freeu', 'ipadapter', 'custom'
  ]

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
          <div className="flex items-center gap-2">
            {/* Source Picker - only show if we have previews with meta */}
            {onApplyFromSource && previews.length > 0 && (
              <SourcePicker
                currentSource={currentSource}
                previews={previews}
                onSelectSource={handleSourceSelect}
              />
            )}
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
        </div>

        {/* Parameters - Categorized in flex grid */}
        {hasParameters ? (
          <div className="flex flex-wrap gap-x-6 gap-y-3 items-start">
            {categoryOrder.map(category => (
              <CategoryGroup
                key={category}
                category={category}
                params={categorizedParams[category]}
                collapsible={!['generation', 'resolution'].includes(category)}
                defaultExpanded={categorizedParams[category].length > 0}
              />
            ))}
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
