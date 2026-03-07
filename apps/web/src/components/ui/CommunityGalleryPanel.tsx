import { useState, useEffect, useMemo } from 'react'
import { useQuery } from '@tanstack/react-query'
import { useTranslation } from 'react-i18next'
import { Loader2, Minimize2, Maximize2 } from 'lucide-react'
import { clsx } from 'clsx'

import { MediaPreview } from './MediaPreview'
import { ThemedSelect } from './ThemedSelect'
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
  const shouldHide = useNsfwStore((s) => s.shouldHide)
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

  // Client-side NSFW filter — shouldHide handles BOTH hide mode AND maxLevel cutoff
  const visibleImages = useMemo(
    () => (images ?? []).filter((img) => !shouldHide(img.nsfw)),
    [images, shouldHide]
  )

  useEffect(() => {
    onImagesChange?.(visibleImages)
  }, [visibleImages, onImagesChange])

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
              {t('community.imageCount', { count: visibleImages.length })}
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
          ) : visibleImages.length ? (
            visibleImages.map((preview, idx) => (
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
