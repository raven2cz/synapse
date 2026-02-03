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
  Layers, Zap, Paintbrush, Grid3X3, Cpu, Box, Image, ImageIcon, FileText, Calculator, Pencil, Bot,
  Lightbulb, AlertTriangle, CheckCircle2,
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

// AI Notes - these are KNOWN AI insight fields with explicit labels.
// IMPORTANT: Unknown fields from AI extraction go to AI Insights AUTOMATICALLY
// via the isAiExtracted && category === 'custom' logic - NO WHITELIST NEEDED!
// This set is only for:
// 1. Fields that need special labels (AI_NOTES_LABELS)
// 2. Fields that would otherwise match PARAM_CATEGORIES but should be AI Notes
const AI_NOTES_KEYS = new Set([
  // Internal
  '_extracted_by',
  // Text notes
  'compatibility',
  'compatibility_notes',
  'usage_tips',
  'warnings',
  'style_notes',
  'quality_notes',
  'best_practices',
  'additional_notes',
  'notes',
  'tips',
  'recommendation',
  'recommendations',
  'resolution_notes',
  // List-based recommendations
  'recommended_models',
  'related_models',
  'recommended_prompts',
  'example_prompts',
  'recommended_resolutions',
  'hires_fix_options',
  'highres_fix_recommendation',
  // Embeddings
  'embeddings',
  'recommended_embeddings',
  'negative_embeddings',
  'positive_embeddings',
  'textual_inversions',
  'avoid_resources',
  'avoid_embeddings',
  // VAE recommendations (override - vae could be in 'model' category but should be AI note)
  'vae',
  'vae_recommendation',
  'recommended_vae',
  // LoRA/Model recommendations
  'loras',
  'recommended_loras',
  'related_loras',
  // Negative prompt suggestions
  'negative_prompt',
  'negative_prompts',
  'recommended_negative',
])

// Labels for AI notes keys (optional - unknown fields get auto-formatted labels)
const AI_NOTES_LABELS: Record<string, string> = {
  compatibility: 'Compatibility',
  compatibility_notes: 'Compatibility Notes',
  usage_tips: 'Usage Tips',
  warnings: 'Warnings',
  recommended_models: 'Recommended Models',
  related_models: 'Related Models',
  highres_fix_recommendation: 'HiRes Fix',
  hires_fix_options: 'HiRes Fix Options',
  style_notes: 'Style Notes',
  quality_notes: 'Quality Notes',
  best_practices: 'Best Practices',
  additional_notes: 'Notes',
  notes: 'Notes',
  tips: 'Tips',
  recommendation: 'Recommendation',
  recommendations: 'Recommendations',
  resolution_notes: 'Resolution Notes',
  recommended_prompts: 'Recommended Prompts',
  example_prompts: 'Example Prompts',
  embeddings: 'Recommended Embeddings',
  recommended_embeddings: 'Recommended Embeddings',
  negative_embeddings: 'Recommended Embeddings',
  positive_embeddings: 'Positive Embeddings',
  textual_inversions: 'Textual Inversions',
  avoid_resources: 'Avoid These',
  avoid_embeddings: 'Avoid Embeddings',
  recommended_resolutions: 'Recommended Resolutions',
  vae: 'Recommended VAE',
  vae_recommendation: 'Recommended VAE',
  recommended_vae: 'Recommended VAE',
  loras: 'Recommended LoRAs',
  recommended_loras: 'Recommended LoRAs',
  related_loras: 'Related LoRAs',
  negative_prompt: 'Negative Prompt',
  negative_prompts: 'Negative Prompts',
  recommended_negative: 'Recommended Negative',
}

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
  // Handle arrays - join with line break for multi-value display
  if (Array.isArray(value)) {
    // Filter out objects, format simple values
    const formatted = value.map(item => {
      if (typeof item === 'object' && item !== null) {
        // For objects, extract meaningful value or skip
        return Object.values(item).filter(v => typeof v !== 'object').join(', ')
      }
      return String(item)
    }).filter(Boolean)
    return formatted.join('\n')
  }
  // Handle objects - extract values
  if (typeof value === 'object' && value !== null) {
    const vals = Object.values(value).filter(v => typeof v !== 'object')
    return vals.join(', ')
  }
  return String(value)
}

function getParamCategory(key: string): CategoryKey {
  for (const [category, keys] of Object.entries(PARAM_CATEGORIES)) {
    if (keys.includes(key)) return category as CategoryKey
  }
  return 'custom'
}

/**
 * Recursively format any value to string (handles nested objects/arrays)
 */
function formatAnyValueRecursive(v: unknown): string {
  if (v === null || v === undefined) return ''
  if (typeof v === 'object') {
    if (Array.isArray(v)) {
      return v.map(item => formatAnyValueRecursive(item)).join(', ')
    }
    // Nested object - format key:value pairs
    return Object.entries(v)
      .map(([k, val]) => `${k}: ${formatAnyValueRecursive(val)}`)
      .join(', ')
  }
  return String(v)
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
      // Get list of fields that came from AI extraction
      const aiFields = (parameters._ai_fields as string[] | undefined) ?? []

      for (const [key, value] of Object.entries(parameters)) {
        if (value === null || value === undefined) continue

        // Skip AI notes - they're displayed in a separate section
        if (AI_NOTES_KEYS.has(key)) continue

        // Skip _raw_* fields and internal fields
        if (key.startsWith('_raw_') || key.startsWith('_')) continue

        // Skip width/height individually if we're showing combined resolution
        if (hasResolution && (key === 'width' || key === 'height')) continue

        const category = getParamCategory(key)
        const isFromAi = aiFields.includes(key)

        // Skip unknown fields from AI extraction - they belong to AI Insights, NOT Custom Parameters!
        // Custom category is ONLY for user-defined parameters, not AI-extracted unknown fields.
        // User-added custom fields (not in _ai_fields) go to Custom.
        if (isFromAi && category === 'custom') continue

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

  // Helper to format AI note values nicely
  const formatNoteValue = useCallback((value: unknown): string => {
    if (value === null || value === undefined) return ''

    // Handle arrays
    if (Array.isArray(value)) {
      // Check if array contains objects
      if (value.length > 0 && typeof value[0] === 'object' && value[0] !== null) {
        // Format each object nicely
        return value.map(item => {
          if (typeof item === 'object' && item !== null) {
            // Extract key values from object, handling nested values
            return Object.entries(item)
              .map(([k, v]) => `${k}: ${formatAnyValueRecursive(v)}`)
              .join(', ')
          }
          return String(item)
        }).join(' • ')
      }
      // Simple array - join with bullet
      return value.map(item => formatAnyValueRecursive(item)).join(' • ')
    }

    // Handle objects
    if (typeof value === 'object' && value !== null) {
      return Object.entries(value)
        .map(([k, v]) => `${k}: ${formatAnyValueRecursive(v)}`)
        .join(', ')
    }

    return String(value)
  }, [])

  // Extract AI notes (text-based metadata from AI extraction)
  // Includes:
  // - AI_NOTES_KEYS (explicit AI note fields)
  // - _raw_* fields (unnormalized data that couldn't be parsed)
  // - Unknown category fields when AI-extracted (not user custom params)
  const aiNotes = useMemo(() => {
    if (!parameters) return []

    const notes: Array<{ key: string; label: string; value: string; isWarning?: boolean; isRaw?: boolean; isList?: boolean; isUnknown?: boolean }> = []
    // Get list of fields that came from AI extraction (to distinguish from user custom fields)
    const aiFields = (parameters._ai_fields as string[] | undefined) ?? []

    for (const [key, value] of Object.entries(parameters)) {
      if (value === null || value === undefined) continue
      if (key === '_extracted_by' || key === '_ai_fields') continue

      // Check field type
      const isAiNote = AI_NOTES_KEYS.has(key)
      const isRawField = key.startsWith('_raw_')
      const isInternalField = key.startsWith('_')
      const category = getParamCategory(key)
      // Unknown fields from AI extraction go to AI Insights (not Custom Parameters)
      // Only include if field is in _ai_fields list (came from AI, not user-added)
      const isFromAi = aiFields.includes(key)
      const isUnknownFromAi = isFromAi && category === 'custom' && !isInternalField

      // Include: explicit AI notes, raw fields, or unknown fields from AI
      if (!isAiNote && !isRawField && !isUnknownFromAi) continue

      const displayValue = formatNoteValue(value)
      const isList = Array.isArray(value) && value.length > 1

      if (displayValue.trim()) {
        // Determine label based on field type
        let label: string
        if (isRawField) {
          const fieldName = key.replace('_raw_', '')
          label = (PARAM_LABELS[fieldName] || fieldName.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase())) + ' (raw)'
        } else if (isUnknownFromAi) {
          // AI-extracted unknown field - nice label
          label = AI_NOTES_LABELS[key] || key.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase())
        } else {
          label = AI_NOTES_LABELS[key] || key.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase())
        }

        notes.push({
          key,
          label,
          value: displayValue,
          isWarning: key === 'warnings' || key.includes('warning') || key.includes('avoid'),
          isRaw: isRawField,
          isList,
          isUnknown: isUnknownFromAi,
        })
      }
    }

    return notes
  }, [parameters, formatNoteValue])

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
          <div className="flex items-center gap-3">
            <h3 className="text-sm font-semibold text-synapse flex items-center gap-2">
              <Sliders className="w-4 h-4" />
              Generation Settings
            </h3>
            {/* Extracted by indicator */}
            {parameters?._extracted_by && (
              <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs bg-slate-dark/50 text-text-muted border border-slate-mid/30">
                <Bot className="w-3 h-3" />
                {parameters._extracted_by}
              </span>
            )}
          </div>
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

        {/* AI Insights Section - extracted tips, recommendations, warnings */}
        {aiNotes.length > 0 && (
          <div className="mt-5 pt-4 border-t border-slate-mid/30">
            <div className="flex items-center gap-2 mb-4">
              <div className="p-1.5 rounded-lg bg-gradient-to-br from-amber-500/20 to-orange-500/10">
                <Lightbulb className="w-4 h-4 text-amber-400" />
              </div>
              <span className="text-sm font-medium text-text-secondary">AI Insights</span>
            </div>

            <div className="space-y-3">
              {aiNotes.map(({ key, label, value, isWarning, isRaw, isList }) => {
                // Determine icon and colors based on content
                const isTip = key.includes('tip') || key.includes('best') || key.includes('usage')
                const isResolution = key.includes('resolution')
                const isAvoid = key.includes('avoid')
                const isCompat = key.includes('compat')
                const isQuality = key.includes('quality') || key.includes('style')

                // Get appropriate icon
                const IconComponent = isWarning || isAvoid ? AlertTriangle
                  : isRaw ? FileText
                  : isTip ? CheckCircle2
                  : isCompat ? Info
                  : isQuality ? Sparkles
                  : isResolution ? Grid3X3
                  : Info

                // Get colors - more subtle
                const iconColor = isWarning || isAvoid ? 'text-amber-400'
                  : isRaw ? 'text-purple-400'
                  : isTip ? 'text-emerald-400'
                  : 'text-slate-400'

                const bgColor = isWarning || isAvoid ? 'bg-amber-500/5'
                  : isRaw ? 'bg-purple-500/5'
                  : isTip ? 'bg-emerald-500/5'
                  : 'bg-slate-800/30'

                // Split tips/text by bullet separator, newline, comma, or sentence for bullet points
                const shouldSplitAsBullets = isTip && (value.includes(' • ') || value.includes('\n') || value.includes(',') || value.includes('.'))
                const bulletItems = shouldSplitAsBullets
                  ? value.split(/ • |[\n,.]/).map(s => s.trim()).filter(s => s.length > 3)
                  : null

                // Split list values for tags
                const listItems = isList && !shouldSplitAsBullets ? value.split(' • ') : null

                return (
                  <div
                    key={key}
                    className={clsx(
                      "rounded-xl p-3 transition-all duration-200",
                      bgColor,
                      "border border-slate-mid/10 hover:border-slate-mid/30"
                    )}
                  >
                    <div className="flex items-start gap-3">
                      <IconComponent className={clsx("w-4 h-4 flex-shrink-0 mt-0.5", iconColor)} />
                      <div className="flex-1 min-w-0">
                        <div className={clsx(
                          "text-xs font-medium mb-1.5 uppercase tracking-wide",
                          isWarning || isAvoid ? "text-amber-400/80" : "text-slate-500"
                        )}>
                          {label}
                        </div>
                        {bulletItems ? (
                          // Render as bullet list for tips
                          <ul className="space-y-1">
                            {bulletItems.map((item, i) => (
                              <li
                                key={i}
                                className="flex items-center gap-2 text-sm text-slate-300/90 leading-relaxed"
                              >
                                <span className="text-emerald-400/60 text-lg leading-none">•</span>
                                <span>{item}</span>
                              </li>
                            ))}
                          </ul>
                        ) : listItems ? (
                          <div className="flex flex-wrap gap-1.5">
                            {listItems.map((item, i) => (
                              <span
                                key={i}
                                className={clsx(
                                  "inline-flex items-center px-2 py-0.5 rounded-md text-xs",
                                  isWarning || isAvoid
                                    ? "bg-amber-500/10 text-amber-300/90"
                                    : "bg-slate-700/50 text-slate-300/80"
                                )}
                              >
                                {item}
                              </span>
                            ))}
                          </div>
                        ) : (
                          <p className="text-sm text-slate-300/80 leading-relaxed">
                            {value}
                          </p>
                        )}
                      </div>
                    </div>
                  </div>
                )
              })}
            </div>
          </div>
        )}
      </Card>
    </div>
  )
}

export default PackParametersSection
