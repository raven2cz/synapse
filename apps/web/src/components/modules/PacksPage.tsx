import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { Link, useNavigate } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import {
  Package, Search, Tag, Plus,
  ZoomIn, ZoomOut, X, AlertTriangle, RefreshCw, Loader2
} from 'lucide-react'
import { clsx } from 'clsx'
import { useSettingsStore } from '@/stores/settingsStore'
import { usePacksStore } from '@/stores/packsStore'
import { useUpdatesStore } from '@/stores/updatesStore'
import { MediaPreview } from '../ui/MediaPreview'
import { BreathingOrb } from '../ui/BreathingOrb'
import { Button } from '../ui/Button'
import { CreatePackModal, type CreatePackData } from './pack-detail/modals'
import { UpdatesPanel } from './packs/UpdatesPanel'
import { toast } from '@/stores/toastStore'

interface PackSummary {
  name: string
  version: string
  description?: string
  installed: boolean
  assets_count: number
  previews_count: number
  nsfw_previews_count: number
  source_url?: string
  created_at?: string
  thumbnail?: string
  thumbnail_type?: 'image' | 'video'
  tags: string[]
  user_tags: string[]
  has_unresolved: boolean
  model_type?: string
  base_model?: string
  is_nsfw?: boolean
  is_nsfw_hidden?: boolean
}

// Special tags with distinct colors
const SPECIAL_TAGS: Record<string, { bg: string; text: string }> = {
  'nsfw-pack': { bg: 'bg-red-500/60', text: 'text-red-100' },
  'nsfw-pack-hide': { bg: 'bg-red-700/60', text: 'text-red-100' },
  'favorites': { bg: 'bg-amber-500/60', text: 'text-amber-100' },
  'to-review': { bg: 'bg-blue-500/60', text: 'text-blue-100' },
  'wip': { bg: 'bg-orange-500/60', text: 'text-orange-100' },
  'archived': { bg: 'bg-slate-500/60', text: 'text-slate-200' },
}

/** Get style for user tag (special or default) */
function getTagStyle(tag: string): string {
  const special = SPECIAL_TAGS[tag.toLowerCase()]
  if (special) {
    return `${special.bg} ${special.text} backdrop-blur-sm`
  }
  return 'bg-pulse/50 text-white backdrop-blur-sm'
}

// Card widths for zoom - fixed sizes
const CARD_WIDTHS = {
  sm: 220,
  md: 300,
  lg: 380,
}

type CardSize = keyof typeof CARD_WIDTHS

export function PacksPage() {
  const { t } = useTranslation()
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const { nsfwBlurEnabled } = useSettingsStore()
  const { searchQuery, selectedTag, setSearchQuery, setSelectedTag } = usePacksStore()
  const [cardSize, setCardSize] = useState<CardSize>('md')
  const [fullscreenImage, setFullscreenImage] = useState<string | null>(null)
  const [isCreateModalOpen, setIsCreateModalOpen] = useState(false)
  const [isUpdatesPanelOpen, setIsUpdatesPanelOpen] = useState(false)
  const { isChecking, checkProgress, updatesCount, checkAll } = useUpdatesStore()

  const handleCheckUpdates = async () => {
    await checkAll()
    const state = useUpdatesStore.getState()
    if (state.updatesCount > 0) {
      toast.info(t('updates.panel.updatesFound', { count: state.updatesCount }))
      setIsUpdatesPanelOpen(true)
    } else {
      toast.success(t('updates.panel.allUpToDate'))
    }
  }

  // Fetch packs
  const { data: packs = [], isLoading, error } = useQuery<PackSummary[]>({
    queryKey: ['packs'],
    queryFn: async () => {
      const res = await fetch('/api/packs/')
      if (!res.ok) {
        throw new Error(`Failed to fetch packs: ${res.status}`)
      }
      const data = await res.json()
      return data.packs || data || []
    },
  })

  // Create pack mutation
  const createPackMutation = useMutation({
    mutationFn: async (data: CreatePackData) => {
      const res = await fetch('/api/packs/create', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(data),
      })
      if (!res.ok) {
        const err = await res.json().catch(() => ({ detail: 'Unknown error' }))
        throw new Error(err.detail || 'Failed to create pack')
      }
      return res.json()
    },
    onSuccess: (data) => {
      queryClient.invalidateQueries({ queryKey: ['packs'] })
      setIsCreateModalOpen(false)
      // Navigate to the new pack
      navigate(`/packs/${encodeURIComponent(data.name)}`)
    },
  })

  // Get unique user tags from all packs
  const allUserTags = Array.from(
    new Set(packs.flatMap(p => p.user_tags || []))
  ).sort()

  // Filter packs
  const filteredPacks = packs.filter(pack => {
    // Hide nsfw-pack-hide packs when blur is enabled
    if (nsfwBlurEnabled && (pack.is_nsfw_hidden || pack.user_tags?.includes('nsfw-pack-hide'))) {
      return false
    }

    // Search filter
    if (searchQuery) {
      const q = searchQuery.toLowerCase()
      const matchesName = pack.name.toLowerCase().includes(q)
      const matchesDesc = pack.description?.toLowerCase().includes(q)
      const matchesTags = pack.tags?.some(t => t.toLowerCase().includes(q))
      const matchesUserTags = pack.user_tags?.some(t => t.toLowerCase().includes(q))
      if (!matchesName && !matchesDesc && !matchesTags && !matchesUserTags) return false
    }

    // User tag filter
    if (selectedTag && !pack.user_tags?.includes(selectedTag)) return false

    return true
  })

  // Zoom handlers
  const zoomIn = () => {
    if (cardSize === 'sm') setCardSize('md')
    else if (cardSize === 'md') setCardSize('lg')
  }

  const zoomOut = () => {
    if (cardSize === 'lg') setCardSize('md')
    else if (cardSize === 'md') setCardSize('sm')
  }

  const cardWidth = CARD_WIDTHS[cardSize]

  return (
    <div className="space-y-6">
      {/* Fullscreen image viewer */}
      {fullscreenImage && (
        <div
          className="fixed inset-0 bg-black z-[90] flex items-center justify-center"
          onClick={() => setFullscreenImage(null)}
        >
          <button
            className="absolute top-6 right-6 p-3 bg-white/10 hover:bg-white/20 rounded-full transition-colors z-10"
            onClick={(e) => { e.stopPropagation(); setFullscreenImage(null) }}
          >
            <X className="w-8 h-8 text-white" />
          </button>
          <img
            src={fullscreenImage}
            alt="Fullscreen preview"
            className="max-w-[95vw] max-h-[95vh] object-contain"
            onClick={(e) => e.stopPropagation()}
          />
        </div>
      )}

      {/* Header with zoom and create button */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-text-primary flex items-center gap-3">
            <Package className="w-7 h-7 text-synapse" />
            {t('packs.title')}
          </h1>
          <p className="text-text-muted mt-1">
            {t('packs.subtitle', { count: packs.length })}
          </p>
        </div>

        <div className="flex items-center gap-3">
          {/* Updates badge button */}
          {updatesCount > 0 && (
            <Button
              variant="secondary"
              onClick={() => setIsUpdatesPanelOpen(true)}
              className="relative transition-all duration-200 hover:scale-105"
            >
              <RefreshCw className="w-4 h-4" />
              {t('updates.badge', { count: updatesCount })}
              <span className="absolute -top-1.5 -right-1.5 w-5 h-5 bg-amber-500 text-white text-[10px] font-bold rounded-full flex items-center justify-center">
                {updatesCount}
              </span>
            </Button>
          )}

          {/* Check Updates Button */}
          <Button
            variant="secondary"
            onClick={handleCheckUpdates}
            disabled={isChecking}
            className="transition-all duration-200"
          >
            {isChecking ? (
              <>
                <Loader2 className="w-4 h-4 animate-spin" />
                {checkProgress && checkProgress.total > 0
                  ? `${checkProgress.current}/${checkProgress.total}`
                  : t('updates.checkUpdates')
                }
              </>
            ) : (
              <>
                <RefreshCw className="w-4 h-4" />
                {t('updates.checkUpdates')}
              </>
            )}
          </Button>

          {/* Create Pack Button */}
          <Button
            variant="primary"
            onClick={() => setIsCreateModalOpen(true)}
            className="transition-all duration-200 hover:scale-105 hover:shadow-lg hover:shadow-synapse/20"
          >
            <Plus className="w-4 h-4" />
            {t('packs.create')}
          </Button>

          {/* Zoom controls */}
          <div className="flex items-center gap-1 bg-slate-dark/80 backdrop-blur rounded-xl p-1 border border-slate-mid/50">
            <button
              onClick={zoomOut}
              disabled={cardSize === 'sm'}
              className="p-2 rounded-lg hover:bg-slate-mid disabled:opacity-30 disabled:cursor-not-allowed transition-colors"
              title={t('packs.zoom.out')}
            >
              <ZoomOut className="w-4 h-4 text-text-secondary" />
            </button>
            <div className="w-px h-6 bg-slate-mid" />
            <button
              onClick={zoomIn}
              disabled={cardSize === 'lg'}
              className="p-2 rounded-lg hover:bg-slate-mid disabled:opacity-30 disabled:cursor-not-allowed transition-colors"
              title={t('packs.zoom.in')}
            >
              <ZoomIn className="w-4 h-4 text-text-secondary" />
            </button>
          </div>
        </div>
      </div>

      {/* Search and filters */}
      <div className="flex flex-wrap gap-4">
        {/* Search */}
        <div className="flex-1 min-w-[300px] relative">
          <Search className="absolute left-4 top-1/2 -translate-y-1/2 w-5 h-5 text-text-muted" />
          <input
            type="text"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            placeholder={t('packs.search')}
            className="w-full pl-12 pr-4 py-3 bg-slate-dark border border-slate-mid rounded-xl text-text-primary placeholder-text-muted focus:outline-none focus:border-synapse transition-colors"
          />
        </div>

        {/* User tag filter */}
        {allUserTags.length > 0 && (
          <select
            value={selectedTag}
            onChange={(e) => setSelectedTag(e.target.value)}
            className="px-4 py-3 bg-slate-dark border border-slate-mid rounded-xl text-text-primary focus:outline-none focus:border-synapse cursor-pointer"
          >
            <option value="">{t('packs.filter.allTags')}</option>
            {allUserTags.map(tag => (
              <option key={tag} value={tag}>{tag}</option>
            ))}
          </select>
        )}
      </div>

      {/* Active filters display */}
      {selectedTag && (
        <div className="flex items-center gap-2 flex-wrap">
          <span className="text-sm text-text-muted">{t('packs.filter.activeFilters')}:</span>
          <button
            onClick={() => setSelectedTag('')}
            className="px-3 py-1 bg-pulse/20 text-pulse rounded-lg text-sm flex items-center gap-1 hover:bg-pulse/30"
          >
            <Tag className="w-3 h-3" />
            {selectedTag}
            <X className="w-3 h-3" />
          </button>
        </div>
      )}

      {/* Loading */}
      {isLoading && (
        <BreathingOrb size="lg" text={t('common.loading')} className="py-16" />
      )}

      {/* Error */}
      {error && (
        <div className="bg-red-900/20 border border-red-500/50 rounded-xl p-4 text-red-400">
          <p className="font-medium">{t('errors.loadFailed')}</p>
          <p className="text-sm mt-1">{(error as Error).message}</p>
        </div>
      )}

      {/* Packs grid - CIVITAI STYLE */}
      <div className="flex flex-wrap gap-4">
        {filteredPacks.map(pack => {
          const thumbnailUrl = pack.thumbnail
          // Check NSFW status from API flag OR user_tags
          const isNsfwPack = pack.is_nsfw || pack.user_tags?.includes('nsfw-pack') || pack.nsfw_previews_count > 0

          return (
            <Link
              key={pack.name}
              to={`/packs/${encodeURIComponent(pack.name)}`}
              className="group cursor-pointer"
              style={{ width: cardWidth }}
            >
              {/* Card - Civitai style with Border + Inner Glow hover effect */}
              <div className={clsx(
                "relative aspect-[3/4] rounded-2xl overflow-hidden bg-slate-dark",
                "transition-all duration-300 ease-out",
                "shadow-md shadow-black/30",
                "group-hover:scale-[1.03]",
                "group-hover:shadow-[inset_0_0_40px_rgba(102,126,234,0.3),0_0_0_2px_rgba(102,126,234,0.6),0_8px_24px_rgba(102,126,234,0.3)]"
              )}>
                {/* Media preview with video autoPlay support */}
                {thumbnailUrl ? (
                  <MediaPreview
                    src={thumbnailUrl}
                    type={pack.thumbnail_type || 'image'}
                    nsfw={isNsfwPack}
                    aspectRatio="portrait"
                    className="w-full h-full"
                    autoPlay={true}
                    playFullOnHover={true}
                  />
                ) : (
                  <div className="w-full h-full flex items-center justify-center bg-gradient-to-br from-slate-dark to-slate-mid">
                    <Package className="w-16 h-16 text-slate-mid" />
                  </div>
                )}

                {/* Gradient overlay */}
                <div className="absolute inset-0 bg-gradient-to-t from-black/90 via-black/30 to-transparent pointer-events-none" />

                {/* Top badges */}
                <div className="absolute top-3 left-3 flex gap-1.5 flex-wrap max-w-[80%]">
                  <span className="px-2 py-1 bg-black/60 backdrop-blur-sm rounded-lg text-xs text-white font-semibold">
                    {t('packs.card.assets', { count: pack.assets_count })}
                  </span>
                </div>

                {/* Unresolved warning */}
                {pack.has_unresolved && (
                  <div className="absolute top-3 right-3">
                    <span className="px-2 py-1 bg-amber-500/90 backdrop-blur-sm rounded-lg text-xs text-white font-semibold flex items-center gap-1 animate-breathe">
                      <AlertTriangle className="w-3 h-3" />
                      {t('packs.card.needsSetup')}
                    </span>
                  </div>
                )}

                {/* User tags with special colors */}
                {pack.user_tags && pack.user_tags.length > 0 && (
                  <div className="absolute top-12 left-3 flex gap-1 flex-wrap max-w-[90%]">
                    {pack.user_tags.slice(0, 3).map(tag => (
                      <span
                        key={tag}
                        className={clsx(
                          'px-2 py-0.5 rounded text-xs',
                          getTagStyle(tag)
                        )}
                      >
                        {tag}
                      </span>
                    ))}
                  </div>
                )}

                {/* Bottom content */}
                <div className="absolute bottom-0 left-0 right-0 p-3 space-y-2">
                  {/* Title */}
                  <h3 className="font-bold text-white text-sm leading-tight line-clamp-2 drop-shadow-lg">
                    {pack.name}
                  </h3>

                  {/* Model type and base model badges */}
                  <div className="flex items-center gap-1.5 flex-wrap">
                    {pack.model_type && (
                      <span className="px-2 py-0.5 bg-synapse/80 rounded text-xs text-white font-medium">
                        {pack.model_type}
                      </span>
                    )}
                    {pack.base_model && (
                      <span className="px-2 py-0.5 bg-white/20 rounded text-xs text-white/90">
                        {pack.base_model}
                      </span>
                    )}
                    <span className="px-2 py-0.5 bg-white/10 rounded text-xs text-white/70">
                      v{pack.version}
                    </span>
                  </div>
                </div>
              </div>
            </Link>
          )
        })}
      </div>

      {/* Empty state */}
      {!isLoading && filteredPacks.length === 0 && (
        <div className="text-center py-12">
          <Package className="w-16 h-16 text-slate-mid mx-auto mb-4" />
          <p className="text-text-muted mb-4">
            {packs.length === 0
              ? t('packs.empty.noPacks')
              : t('packs.empty.noMatch')}
          </p>
          {packs.length === 0 && (
            <Button
              variant="primary"
              onClick={() => setIsCreateModalOpen(true)}
              className="transition-all duration-200 hover:scale-105"
            >
              <Plus className="w-4 h-4" />
              {t('packs.create')}
            </Button>
          )}
        </div>
      )}

      {/* Create Pack Modal */}
      <CreatePackModal
        isOpen={isCreateModalOpen}
        onClose={() => setIsCreateModalOpen(false)}
        onCreate={createPackMutation.mutateAsync}
        isCreating={createPackMutation.isPending}
      />

      {/* Updates Panel */}
      <UpdatesPanel
        open={isUpdatesPanelOpen}
        onClose={() => setIsUpdatesPanelOpen(false)}
      />
    </div>
  )
}
