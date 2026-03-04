import { useState, useEffect, useRef, useCallback } from 'react'
import { useQuery } from '@tanstack/react-query'
import { useTranslation } from 'react-i18next'
import { Loader2, ChevronDown, Check, Minimize2, Maximize2 } from 'lucide-react'
import { clsx } from 'clsx'

import { MediaPreview } from './MediaPreview'
import { useNsfwStore } from '@/stores/nsfwStore'
import { getAdapter } from '@/lib/api/searchAdapters'
import type { SearchProvider, ModelPreview } from '@/lib/api/searchTypes'

// =============================================================================
// Sort / Period options for community gallery
// =============================================================================

const COMMUNITY_SORT_OPTIONS = [
  { value: 'Most Reactions', i18nKey: 'community.sort.mostReactions' },
  { value: 'Most Comments', i18nKey: 'community.sort.mostComments' },
  { value: 'Most Collected', i18nKey: 'community.sort.mostCollected' },
  { value: 'Newest', i18nKey: 'community.sort.newest' },
  { value: 'Oldest', i18nKey: 'community.sort.oldest' },
] as const

const COMMUNITY_PERIOD_OPTIONS = [
  { value: 'AllTime', i18nKey: 'community.period.allTime' },
  { value: 'Year', i18nKey: 'community.period.year' },
  { value: 'Month', i18nKey: 'community.period.month' },
  { value: 'Week', i18nKey: 'community.period.week' },
  { value: 'Day', i18nKey: 'community.period.day' },
] as const

const LIMIT_OPTIONS = [20, 50, 100, 150, 200] as const

const BROWSING_LEVEL_OPTIONS = [
  { value: 'auto' as const, i18nKey: 'community.browsingLevel.auto' },
  { value: 1, i18nKey: 'community.browsingLevel.pg' },
  { value: 3, i18nKey: 'community.browsingLevel.pg13' },
  { value: 7, i18nKey: 'community.browsingLevel.r' },
  { value: 15, i18nKey: 'community.browsingLevel.x' },
  { value: 31, i18nKey: 'community.browsingLevel.all' },
] as const

// =============================================================================
// ThemedSelect — glass-morphism dropdown (local to this component)
// =============================================================================

interface ThemedSelectProps<T extends string | number> {
  value: T
  options: { value: T; label: string }[]
  onChange: (value: T) => void
  className?: string
}

function ThemedSelect<T extends string | number>({
  value,
  options,
  onChange,
  className,
}: ThemedSelectProps<T>) {
  const [isOpen, setIsOpen] = useState(false)
  const ref = useRef<HTMLDivElement>(null)

  const handleClickOutside = useCallback((e: MouseEvent) => {
    if (ref.current && !ref.current.contains(e.target as Node)) {
      setIsOpen(false)
    }
  }, [])

  useEffect(() => {
    document.addEventListener('mousedown', handleClickOutside)
    return () => document.removeEventListener('mousedown', handleClickOutside)
  }, [handleClickOutside])

  const selectedLabel = options.find((o) => o.value === value)?.label ?? String(value)

  return (
    <div className={clsx('relative', className)} ref={ref}>
      <button
        onClick={() => setIsOpen(!isOpen)}
        className={clsx(
          'flex items-center gap-1.5 px-2.5 py-1 rounded-lg text-xs',
          'bg-slate-dark/80 backdrop-blur border border-slate-mid/50',
          'text-text-primary hover:bg-slate-mid/50 transition-colors duration-150',
          'cursor-pointer select-none'
        )}
      >
        <span className="truncate max-w-[120px]">{selectedLabel}</span>
        <ChevronDown className={clsx('w-3.5 h-3.5 opacity-60 transition-transform duration-150', isOpen && 'rotate-180')} />
      </button>
      {isOpen && (
        <div
          className={clsx(
            'absolute top-full mt-1.5 min-w-[160px] p-1',
            'bg-slate-darker/95 backdrop-blur-xl',
            'border border-slate-mid/30 rounded-xl',
            'shadow-xl shadow-black/30',
            'z-[9999] overflow-y-auto max-h-[240px]'
          )}
        >
          {options.map((opt) => (
            <button
              key={String(opt.value)}
              onClick={() => {
                onChange(opt.value)
                setIsOpen(false)
              }}
              className={clsx(
                'w-full flex items-center gap-2 px-3 py-1.5 rounded-lg text-xs text-left',
                'transition-colors duration-150',
                opt.value === value
                  ? 'bg-synapse/20 text-synapse'
                  : 'text-text-secondary hover:bg-slate-mid/50 hover:text-text-primary'
              )}
            >
              <span className="flex-1">{opt.label}</span>
              {opt.value === value && <Check className="w-3.5 h-3.5 flex-shrink-0" />}
            </button>
          ))}
        </div>
      )}
    </div>
  )
}

// =============================================================================
// Props
// =============================================================================

interface CommunityGalleryPanelProps {
  modelId: number
  versionId: number
  searchProvider: SearchProvider
  onImagesChange?: (images: ModelPreview[]) => void
  onImageClick?: (index: number) => void
  columns?: number
  maxHeight?: string
  className?: string
}

// =============================================================================
// Component
// =============================================================================

export function CommunityGalleryPanel({
  modelId,
  versionId,
  searchProvider,
  onImagesChange,
  onImageClick,
  columns = 6,
  maxHeight = '360px',
  className,
}: CommunityGalleryPanelProps) {
  const { t } = useTranslation()

  const [communitySort, setCommunitySort] = useState('Most Reactions')
  const [communityPeriod, setCommunityPeriod] = useState('AllTime')
  const [communityLimit, setCommunityLimit] = useState(50)
  const [communityBrowsingLevel, setCommunityBrowsingLevel] = useState<number | 'auto'>('auto')
  const [isCollapsed, setIsCollapsed] = useState(false)

  const storeBrowsingLevel = useNsfwStore((s) => s.getBrowsingLevel())
  const effectiveBrowsingLevel = communityBrowsingLevel === 'auto'
    ? storeBrowsingLevel
    : communityBrowsingLevel

  const { data: images, isLoading } = useQuery<ModelPreview[]>({
    queryKey: [
      'civitai-community-gallery',
      modelId,
      versionId,
      communitySort,
      communityPeriod,
      effectiveBrowsingLevel,
      communityLimit,
    ],
    queryFn: () =>
      getAdapter(searchProvider).getModelPreviews!(modelId, versionId, {
        limit: communityLimit,
        sort: communitySort,
        period: communityPeriod,
        browsingLevel: effectiveBrowsingLevel,
      }),
    staleTime: 5 * 60 * 1000,
  })

  useEffect(() => {
    if (images) onImagesChange?.(images)
  }, [images, onImagesChange])

  // Build option arrays for ThemedSelect
  const sortOptions = COMMUNITY_SORT_OPTIONS.map((opt) => ({
    value: opt.value,
    label: t(opt.i18nKey),
  }))

  const periodOptions = COMMUNITY_PERIOD_OPTIONS.map((opt) => ({
    value: opt.value,
    label: t(opt.i18nKey),
  }))

  const limitOptions = LIMIT_OPTIONS.map((v) => ({
    value: v,
    label: t('community.limit.posts', { count: v }),
  }))

  const browsingLevelOptions = BROWSING_LEVEL_OPTIONS.map((opt) => ({
    value: opt.value,
    label: t(opt.i18nKey),
  }))

  return (
    <div className={className}>
      {/* Toolbar */}
      <div className="flex items-center gap-2 mb-2 flex-wrap">
        <ThemedSelect
          value={communitySort}
          options={sortOptions}
          onChange={(v) => setCommunitySort(v)}
        />

        <ThemedSelect
          value={communityPeriod}
          options={periodOptions}
          onChange={(v) => setCommunityPeriod(v)}
        />

        <ThemedSelect
          value={communityLimit}
          options={limitOptions}
          onChange={(v) => setCommunityLimit(v)}
        />

        <ThemedSelect
          value={communityBrowsingLevel}
          options={browsingLevelOptions}
          onChange={(v) => setCommunityBrowsingLevel(v)}
        />

        {/* Image count + collapse toggle on right */}
        <div className="flex items-center gap-2 ml-auto">
          {images && !isLoading && (
            <span className="text-xs text-text-muted">
              {t('community.imageCount', { count: images.length })}
              {images.length > communityLimit && (
                <span className="text-text-muted/60">
                  {' · '}{t('community.limit.posts', { count: communityLimit })}
                </span>
              )}
            </span>
          )}

          {isLoading && (
            <Loader2 className="w-3.5 h-3.5 text-text-muted animate-spin" />
          )}

          <button
            onClick={() => setIsCollapsed(!isCollapsed)}
            className={clsx(
              'flex items-center gap-1.5 px-2.5 py-1 rounded-lg',
              'text-xs text-text-muted',
              'bg-slate-mid/30 hover:bg-slate-mid/50',
              'transition-colors duration-200'
            )}
            title={isCollapsed ? t('community.expand') : t('community.collapse')}
          >
            {isCollapsed ? (
              <>
                <Maximize2 className="w-3.5 h-3.5" />
                {t('community.expand')}
              </>
            ) : (
              <>
                <Minimize2 className="w-3.5 h-3.5" />
                {t('community.collapse')}
              </>
            )}
          </button>
        </div>
      </div>

      {/* Image grid - animated collapse/expand */}
      <div
        className={clsx(
          'transition-[max-height] duration-300 ease-in-out overflow-hidden',
          isCollapsed
            ? 'overflow-y-auto scrollbar-thin scrollbar-thumb-slate-mid scrollbar-track-transparent'
            : 'max-h-[10000px]'
        )}
        style={isCollapsed ? { maxHeight } : undefined}
      >
        <div
          className="p-1"
          style={{
            display: 'grid',
            gridTemplateColumns: `repeat(${columns}, minmax(0, 1fr))`,
            gap: '0.75rem',
          }}
        >
          {isLoading ? (
            Array.from({ length: columns }).map((_, i) => (
              <div
                key={i}
                className="aspect-[3/4] rounded-xl bg-slate-mid/30 animate-pulse"
              />
            ))
          ) : images?.length ? (
            images.map((preview, idx) => (
              <MediaPreview
                key={idx}
                src={preview.url}
                type={preview.media_type}
                thumbnailSrc={preview.thumbnail_url}
                nsfw={preview.nsfw}
                aspectRatio="portrait"
                className="cursor-pointer hover:ring-2 ring-synapse"
                autoPlay={true}
                onClick={onImageClick ? () => onImageClick(idx) : undefined}
              />
            ))
          ) : (
            <div
              className="text-center py-8 text-text-muted text-sm"
              style={{ gridColumn: `1 / -1` }}
            >
              {t('community.noImages')}
            </div>
          )}
        </div>
      </div>

      {/* Fade overlay when collapsed */}
      <div
        className={clsx(
          'relative h-8 -mt-8 pointer-events-none',
          'bg-gradient-to-t from-obsidian to-transparent',
          'transition-opacity duration-300',
          isCollapsed ? 'opacity-100' : 'opacity-0'
        )}
      />
    </div>
  )
}
