/**
 * PackInfoSection
 *
 * Displays pack metadata: trigger words, model info, and description.
 *
 * FUNKCE ZACHOVÁNY:
 * - Trigger words s copy to clipboard
 * - Model info badges (type, base model, downloads, rating)
 * - Usage tips zobrazení
 * - HTML description rendering (dangerouslySetInnerHTML pro Civitai)
 *
 * VIZUÁLNĚ VYLEPŠENO:
 * - Premium karty s hover efekty
 * - Lepší badge styling
 * - Animované copy feedback
 * - Staggered entrance animace
 */

import { useState } from 'react'
import { Copy, Check, Download, Star, Info, Sparkles, Wand2 } from 'lucide-react'
import { clsx } from 'clsx'
import { Card } from '@/components/ui/Card'
import { toast } from '@/stores/toastStore'
import type { PackDetail, ModelInfoResponse } from '../types'
import { ANIMATION_PRESETS } from '../constants'

// =============================================================================
// Types
// =============================================================================

export interface PackInfoSectionProps {
  /**
   * Pack data to display
   */
  pack: PackDetail

  /**
   * Base animation delay for staggered entrance
   */
  animationDelay?: number
}

// =============================================================================
// Sub-components
// =============================================================================

interface TriggerWordChipProps {
  word: string
}

function TriggerWordChip({ word }: TriggerWordChipProps) {
  const [copied, setCopied] = useState(false)

  const handleCopy = () => {
    navigator.clipboard.writeText(word)
    setCopied(true)
    toast.success(`Copied: ${word}`)
    setTimeout(() => setCopied(false), 2000)
  }

  return (
    <button
      onClick={handleCopy}
      className={clsx(
        'px-3 py-1.5 rounded-lg text-sm',
        'flex items-center gap-2',
        'transition-all duration-200',
        'border',
        copied
          ? 'bg-green-500/20 text-green-400 border-green-500/30'
          : 'bg-synapse/20 text-synapse border-synapse/30 hover:bg-synapse/30 hover:scale-105'
      )}
    >
      <code className="font-mono">{word}</code>
      {copied ? (
        <Check className="w-3.5 h-3.5" />
      ) : (
        <Copy className="w-3.5 h-3.5 opacity-60" />
      )}
    </button>
  )
}

interface TriggerWordsCardProps {
  triggerWords: string[]
  animationDelay: number
}

function TriggerWordsCard({ triggerWords, animationDelay }: TriggerWordsCardProps) {
  if (!triggerWords?.length) return null

  return (
    <div
      className={ANIMATION_PRESETS.sectionEnter}
      style={{ animationDelay: `${animationDelay}ms`, animationFillMode: 'both' }}
    >
      <Card className="p-4">
        <h3 className="text-sm font-semibold text-text-primary mb-3 flex items-center gap-2">
          <Wand2 className="w-4 h-4 text-synapse" />
          Trigger Words
        </h3>
        <div className="flex flex-wrap gap-2">
          {triggerWords.map((word, idx) => (
            <TriggerWordChip key={idx} word={word} />
          ))}
        </div>
      </Card>
    </div>
  )
}

interface ModelInfoCardProps {
  modelInfo: ModelInfoResponse
  animationDelay: number
}

function ModelInfoCard({ modelInfo, animationDelay }: ModelInfoCardProps) {
  const hasContent = modelInfo.model_type ||
    modelInfo.base_model ||
    (modelInfo.download_count != null && modelInfo.download_count > 0) ||
    (modelInfo.rating != null && modelInfo.rating > 0) ||
    modelInfo.usage_tips

  if (!hasContent) return null

  return (
    <div
      className={ANIMATION_PRESETS.sectionEnter}
      style={{ animationDelay: `${animationDelay}ms`, animationFillMode: 'both' }}
    >
      <Card className="p-4">
        <h3 className="text-sm font-semibold text-text-primary mb-3 flex items-center gap-2">
        <Info className="w-4 h-4 text-pulse" />
        Model Info
      </h3>

      <div className="space-y-3">
        {/* Badges Row */}
        <div className="flex flex-wrap gap-2">
          {modelInfo.model_type && (
            <span className={clsx(
              'px-3 py-1 rounded-lg text-sm font-medium',
              'bg-synapse/20 text-synapse border border-synapse/30',
              'flex items-center gap-1.5',
              'transition-transform duration-200 hover:scale-105'
            )}>
              <Sparkles className="w-3.5 h-3.5" />
              {modelInfo.model_type}
            </span>
          )}

          {modelInfo.base_model && (
            <span className={clsx(
              'px-3 py-1 rounded-lg text-sm',
              'bg-pulse/20 text-pulse border border-pulse/30',
              'transition-transform duration-200 hover:scale-105'
            )}>
              Base: {modelInfo.base_model}
            </span>
          )}

          {modelInfo.download_count != null && modelInfo.download_count > 0 && (
            <span className={clsx(
              'px-3 py-1 rounded-lg text-sm',
              'bg-slate-mid/50 text-text-muted border border-slate-mid',
              'flex items-center gap-1.5',
              'transition-transform duration-200 hover:scale-105'
            )}>
              <Download className="w-3.5 h-3.5" />
              {modelInfo.download_count.toLocaleString()}
            </span>
          )}

          {modelInfo.rating != null && modelInfo.rating > 0 && (
            <span className={clsx(
              'px-3 py-1 rounded-lg text-sm',
              'bg-amber-500/20 text-amber-400 border border-amber-500/30',
              'flex items-center gap-1.5',
              'transition-transform duration-200 hover:scale-105'
            )}>
              <Star className="w-3.5 h-3.5" fill="currentColor" />
              {modelInfo.rating.toFixed(1)}
            </span>
          )}
        </div>

        {/* Usage Tips */}
        {modelInfo.usage_tips && (
          <p className="text-text-secondary text-sm leading-relaxed">
            {modelInfo.usage_tips}
          </p>
        )}
      </div>
      </Card>
    </div>
  )
}

interface DescriptionCardProps {
  description: string
  animationDelay: number
}

function DescriptionCard({ description, animationDelay }: DescriptionCardProps) {
  if (!description) return null

  return (
    <div
      className={ANIMATION_PRESETS.sectionEnter}
      style={{ animationDelay: `${animationDelay}ms`, animationFillMode: 'both' }}
    >
      <Card className="p-4">
        <h3 className="text-sm font-semibold text-text-primary mb-3">Description</h3>
        {/*
          ⚠️ KRITICKÉ: HTML rendering pro Civitai importy
          Civitai vrací HTML popis, který musíme renderovat správně.
        */}
        <div
          className={clsx(
            'prose prose-invert prose-sm max-w-none',
            'text-text-secondary',
            // Custom prose styling
            'prose-p:leading-relaxed',
            'prose-a:text-synapse prose-a:no-underline hover:prose-a:underline',
            'prose-strong:text-text-primary',
            'prose-headings:text-text-primary'
          )}
          dangerouslySetInnerHTML={{ __html: description }}
        />
      </Card>
    </div>
  )
}

// =============================================================================
// Main Component
// =============================================================================

export function PackInfoSection({ pack, animationDelay = 0 }: PackInfoSectionProps) {
  const hasTriggerWords = pack.model_info?.trigger_words && pack.model_info.trigger_words.length > 0
  const hasModelInfo = !!pack.model_info
  const hasDescription = !!pack.description

  // Return null if no content
  if (!hasTriggerWords && !hasModelInfo && !hasDescription) {
    return null
  }

  // Stagger delays for each card
  const delays = {
    triggerWords: animationDelay,
    modelInfo: animationDelay + 50,
    description: animationDelay + 100,
  }

  return (
    <div className="space-y-4">
      {/* Trigger Words */}
      {hasTriggerWords && (
        <TriggerWordsCard
          triggerWords={pack.model_info!.trigger_words}
          animationDelay={delays.triggerWords}
        />
      )}

      {/* Model Info */}
      {hasModelInfo && (
        <ModelInfoCard
          modelInfo={pack.model_info!}
          animationDelay={delays.modelInfo}
        />
      )}

      {/* Description */}
      {hasDescription && (
        <DescriptionCard
          description={pack.description!}
          animationDelay={delays.description}
        />
      )}
    </div>
  )
}

export default PackInfoSection
