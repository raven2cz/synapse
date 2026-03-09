/**
 * PreviewAnalysisTab
 *
 * Shows preview images with extracted model hints and generation params.
 * Part of DependencyResolverModal — replaces the former placeholder.
 */

import { useState, useMemo } from 'react'
import { useTranslation } from 'react-i18next'
import {
  Loader2,
  Image as ImageIcon,
  Copy,
  ArrowRight,
  Hash,
  Box,
  Layers,
  Hexagon,
  AlertCircle,
} from 'lucide-react'
import { clsx } from 'clsx'
import { toast } from '@/stores/toastStore'
import { usePreviewAnalysis } from '../hooks/usePreviewAnalysis'
import type {
  AssetType,
  PreviewAnalysisItem,
  PreviewModelHintInfo,
  ResolutionCandidate,
} from '../types'

// =============================================================================
// Types
// =============================================================================

export interface PreviewAnalysisTabProps {
  packName: string
  depKind: AssetType
  candidates: ResolutionCandidate[]
  onSelectCandidate: (candidateId: string) => void
}

// =============================================================================
// Kind display config
// =============================================================================

const KIND_CONFIG: Record<string, { label: string; color: string; bg: string; icon: typeof Box }> = {
  checkpoint: { label: 'Checkpoint', color: 'text-blue-400', bg: 'bg-blue-500/15', icon: Box },
  lora: { label: 'LoRA', color: 'text-purple-400', bg: 'bg-purple-500/15', icon: Layers },
  vae: { label: 'VAE', color: 'text-emerald-400', bg: 'bg-emerald-500/15', icon: Hexagon },
  controlnet: { label: 'ControlNet', color: 'text-amber-400', bg: 'bg-amber-500/15', icon: Layers },
  embedding: { label: 'Embedding', color: 'text-cyan-400', bg: 'bg-cyan-500/15', icon: Hash },
  upscaler: { label: 'Upscaler', color: 'text-pink-400', bg: 'bg-pink-500/15', icon: Layers },
}

function getKindDisplay(kind: string | null) {
  if (!kind) return { label: 'Unknown', color: 'text-text-muted', bg: 'bg-slate-mid/30', icon: AlertCircle }
  return KIND_CONFIG[kind] || { label: kind, color: 'text-text-muted', bg: 'bg-slate-mid/30', icon: AlertCircle }
}

// =============================================================================
// Sub-components
// =============================================================================

function PreviewThumbnail({
  preview,
  isSelected,
  onClick,
}: {
  preview: PreviewAnalysisItem
  isSelected: boolean
  onClick: () => void
}) {
  const hintCount = preview.hints.length

  return (
    <button
      onClick={onClick}
      className={clsx(
        'relative rounded-lg overflow-hidden aspect-square',
        'transition-all duration-200 group',
        isSelected
          ? 'ring-2 ring-synapse ring-offset-1 ring-offset-slate-deep'
          : 'ring-1 ring-slate-mid hover:ring-slate-mid/80'
      )}
    >
      {preview.url ? (
        <img
          src={preview.thumbnail_url || preview.url}
          alt={preview.filename}
          className="w-full h-full object-cover"
          loading="lazy"
        />
      ) : (
        <div className="w-full h-full bg-slate-dark flex items-center justify-center">
          <ImageIcon className="w-6 h-6 text-text-muted/30" />
        </div>
      )}

      {/* Hint count badge */}
      {hintCount > 0 && (
        <span className="absolute top-1 right-1 px-1.5 py-0.5 rounded-full text-[10px] font-bold bg-synapse/90 text-white">
          {hintCount}
        </span>
      )}

      {/* Video indicator */}
      {preview.media_type === 'video' && (
        <span className="absolute bottom-1 left-1 px-1 py-0.5 rounded text-[9px] font-medium bg-black/60 text-white">
          VIDEO
        </span>
      )}
    </button>
  )
}

function HintRow({
  hint,
  depKind,
  onUse,
  canUse,
}: {
  hint: PreviewModelHintInfo
  depKind: AssetType
  onUse: () => void
  canUse: boolean
}) {
  const display = getKindDisplay(hint.kind)
  const KindIcon = display.icon
  const isMatchingKind = hint.kind === depKind || hint.kind === null
  const dimmed = !hint.resolvable

  return (
    <div
      className={clsx(
        'flex items-center gap-2 py-1.5 px-2 rounded-md',
        dimmed ? 'opacity-50' : 'hover:bg-slate-mid/20'
      )}
    >
      <KindIcon className={clsx('w-3.5 h-3.5 flex-shrink-0', display.color)} />
      <span className="text-sm text-text-primary truncate flex-1 font-mono" title={hint.raw_value}>
        {hint.filename}
      </span>

      {/* Kind badge */}
      <span className={clsx('px-1.5 py-0.5 rounded text-[10px] font-medium', display.bg, display.color)}>
        {display.label}
      </span>

      {/* Hash */}
      {hint.hash && (
        <span className="text-[10px] text-text-muted font-mono" title={`Hash: ${hint.hash}`}>
          {hint.hash.slice(0, 8)}
        </span>
      )}

      {/* Weight */}
      {hint.weight != null && (
        <span className="text-[10px] text-text-muted">
          w:{hint.weight}
        </span>
      )}

      {/* Use button */}
      {isMatchingKind && canUse && !dimmed && (
        <button
          onClick={onUse}
          className="flex items-center gap-1 px-2 py-0.5 rounded text-xs font-medium text-synapse hover:bg-synapse/10 transition-colors"
          title="Use this model reference"
        >
          Use
          <ArrowRight className="w-3 h-3" />
        </button>
      )}

      {dimmed && (
        <span className="text-[10px] text-text-muted italic">unresolvable</span>
      )}
    </div>
  )
}

function GenerationParamsDisplay({ params }: { params: Record<string, any> }) {
  const { t } = useTranslation()

  // Key display items
  const items: [string, string | number][] = []
  if (params.sampler) items.push(['Sampler', params.sampler])
  if (params.steps) items.push(['Steps', params.steps])
  if (params.cfgScale || params.cfg_scale) items.push(['CFG', params.cfgScale || params.cfg_scale])
  if (params.seed) items.push(['Seed', params.seed])
  if (params.Size) items.push(['Size', params.Size])
  if (params['Clip skip']) items.push(['Clip skip', params['Clip skip']])
  if (params['Denoising strength']) items.push(['Denoise', params['Denoising strength']])

  const prompt = params.prompt
  const negativePrompt = params.negativePrompt || params.negative_prompt

  const handleCopyPrompt = () => {
    if (prompt) {
      navigator.clipboard.writeText(prompt).then(
        () => toast.success(t('common.copied', 'Copied to clipboard')),
        () => toast.error(t('common.copyFailed', 'Failed to copy'))
      )
    }
  }

  return (
    <div className="space-y-2">
      {/* Param grid */}
      {items.length > 0 && (
        <div className="flex flex-wrap gap-x-4 gap-y-1">
          {items.map(([label, value]) => (
            <span key={label} className="text-xs">
              <span className="text-text-muted">{label}:</span>{' '}
              <span className="text-text-primary font-mono">{String(value)}</span>
            </span>
          ))}
        </div>
      )}

      {/* Prompt */}
      {prompt && (
        <div className="mt-2">
          <div className="flex items-center justify-between mb-1">
            <span className="text-xs text-text-muted font-medium">Prompt</span>
            <button
              onClick={handleCopyPrompt}
              className="flex items-center gap-1 text-xs text-text-muted hover:text-text-primary transition-colors"
            >
              <Copy className="w-3 h-3" />
              Copy
            </button>
          </div>
          <p className="text-xs text-text-primary/80 line-clamp-3 font-mono bg-slate-dark/50 rounded px-2 py-1.5">
            {prompt}
          </p>
        </div>
      )}

      {/* Negative prompt */}
      {negativePrompt && (
        <div>
          <span className="text-xs text-text-muted font-medium">Negative</span>
          <p className="text-xs text-text-muted/70 line-clamp-2 font-mono bg-slate-dark/50 rounded px-2 py-1 mt-0.5">
            {negativePrompt}
          </p>
        </div>
      )}
    </div>
  )
}

// =============================================================================
// Main Component
// =============================================================================

export function PreviewAnalysisTab({
  packName,
  depKind,
  candidates,
  onSelectCandidate,
}: PreviewAnalysisTabProps) {
  const { t } = useTranslation()
  const [selectedIndex, setSelectedIndex] = useState<number | null>(null)

  const { data, isLoading, error } = usePreviewAnalysis(packName, true)

  // Filter previews that have hints
  const previewsWithHints = useMemo(() => {
    if (!data?.previews) return []
    return data.previews
  }, [data])

  const selectedPreview = selectedIndex !== null && selectedIndex < previewsWithHints.length
    ? previewsWithHints[selectedIndex] : null

  // Find matching candidate for a hint
  const findCandidateForHint = (hint: PreviewModelHintInfo): string | null => {
    // Look for a candidate whose evidence references this preview hint
    for (const c of candidates) {
      for (const g of c.evidence_groups) {
        // Check provenance — preview evidence has "preview:<filename>" pattern
        if (g.provenance.startsWith('preview:')) {
          for (const item of g.items) {
            if (
              item.raw_value &&
              (item.raw_value === hint.raw_value ||
                item.raw_value === hint.filename)
            ) {
              return c.candidate_id
            }
          }
        }
      }
      // Also try matching by display name
      const normalized = hint.filename.replace(/\.safetensors$|\.ckpt$|\.pt$/i, '').toLowerCase()
      if (c.display_name.toLowerCase().includes(normalized)) {
        return c.candidate_id
      }
    }
    return null
  }

  const handleUseHint = (hint: PreviewModelHintInfo) => {
    const candidateId = findCandidateForHint(hint)
    if (candidateId) {
      onSelectCandidate(candidateId)
    } else {
      toast.info(
        t('pack.resolve.previewRunSuggest', 'No matching candidate found. Run suggestion first.')
      )
    }
  }

  // Loading state
  if (isLoading) {
    return (
      <div className="flex flex-col items-center justify-center py-12 gap-3">
        <Loader2 className="w-8 h-8 text-synapse animate-spin" />
        <p className="text-sm text-text-muted">
          {t('pack.resolve.previewLoading', 'Analyzing preview images...')}
        </p>
      </div>
    )
  }

  // Error state
  if (error) {
    return (
      <div className="flex flex-col items-center justify-center py-12 gap-3">
        <AlertCircle className="w-8 h-8 text-red-400" />
        <p className="text-sm text-red-400">{error.message}</p>
      </div>
    )
  }

  // Empty state
  if (!data || previewsWithHints.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center py-12 gap-3">
        <ImageIcon className="w-10 h-10 text-text-muted/50" />
        <p className="text-text-muted text-center">
          {t('pack.resolve.noPreviewData', 'No preview metadata available for this dependency.')}
        </p>
      </div>
    )
  }

  return (
    <div className="space-y-4">
      {/* Header */}
      <div className="flex items-center justify-between">
        <p className="text-sm text-text-muted">
          {t('pack.resolve.previewHintsCount', '{{count}} model hints from {{total}} previews', {
            count: data.total_hints,
            total: previewsWithHints.length,
          })}
        </p>
      </div>

      {/* Thumbnail grid */}
      <div className="grid grid-cols-5 sm:grid-cols-6 md:grid-cols-8 gap-2">
        {previewsWithHints.map((preview, index) => (
          <PreviewThumbnail
            key={preview.filename}
            preview={preview}
            isSelected={selectedIndex === index}
            onClick={() => setSelectedIndex(selectedIndex === index ? null : index)}
          />
        ))}
      </div>

      {/* Selected preview detail panel */}
      {selectedPreview && (
        <div className="rounded-xl bg-slate-dark border border-slate-mid overflow-hidden">
          {/* Header */}
          <div className="flex items-center justify-between px-4 py-3 border-b border-slate-mid">
            <div className="flex items-center gap-2 min-w-0">
              <ImageIcon className="w-4 h-4 text-synapse flex-shrink-0" />
              <span className="text-sm text-text-primary font-medium truncate">
                {selectedPreview.filename}
              </span>
            </div>
            {(selectedPreview.width || selectedPreview.height) && (
              <span className="text-xs text-text-muted flex-shrink-0">
                {selectedPreview.width}&times;{selectedPreview.height}
              </span>
            )}
          </div>

          <div className="p-4 space-y-4">
            {/* Model References */}
            {selectedPreview.hints.length > 0 && (
              <div>
                <h4 className="text-xs text-text-muted font-medium uppercase tracking-wider mb-2">
                  {t('pack.resolve.previewModelRefs', 'Model References')}
                </h4>
                <div className="space-y-0.5">
                  {selectedPreview.hints.map((hint, i) => (
                    <HintRow
                      key={`${hint.filename}-${i}`}
                      hint={hint}
                      depKind={depKind}
                      onUse={() => handleUseHint(hint)}
                      canUse={candidates.length > 0}
                    />
                  ))}
                </div>
              </div>
            )}

            {/* No hints for this preview */}
            {selectedPreview.hints.length === 0 && (
              <p className="text-sm text-text-muted italic">
                {t('pack.resolve.previewNoHints', 'No model references found in this preview.')}
              </p>
            )}

            {/* Generation Parameters */}
            {selectedPreview.generation_params && Object.keys(selectedPreview.generation_params).length > 0 && (
              <div>
                <h4 className="text-xs text-text-muted font-medium uppercase tracking-wider mb-2">
                  {t('pack.resolve.previewGenParams', 'Generation Parameters')}
                </h4>
                <GenerationParamsDisplay params={selectedPreview.generation_params} />
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  )
}

export default PreviewAnalysisTab
