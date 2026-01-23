import { useState, useEffect, useRef, useCallback } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import {
  Search, Download, X, ExternalLink,
  User, Heart, Loader2, AlertCircle, CheckCircle, Info, Copy,
  ZoomIn, ZoomOut, ThumbsUp
} from 'lucide-react'
import { Button } from '@/components/ui/Button'
import { clsx } from 'clsx'

import { MediaPreview } from '@/components/ui/MediaPreview'
import { FullscreenMediaViewer } from '@/components/ui/FullscreenMediaViewer'
import { ImportWizardModal } from '@/components/ui/ImportWizardModal'
import { SearchFilters } from '@/components/ui/SearchFilters'
import { BreathingOrb } from '@/components/ui/BreathingOrb'

import type { MediaType } from '@/lib/media'
import type { SearchProvider, SortOption, PeriodOption } from '@/lib/api/searchTypes'
import { getAdapter, isProviderAvailable, getDefaultProvider } from '@/lib/api/searchAdapters'

interface ModelPreview {
  url: string
  nsfw: boolean
  width?: number
  height?: number
  meta?: Record<string, any>
  media_type?: MediaType
  duration?: number
  thumbnail_url?: string
}

interface ModelFile {
  id: number
  name: string
  size_kb?: number
  download_url?: string
  hash_autov2?: string
  hash_sha256?: string
}

interface ModelVersion {
  id: number
  name: string
  base_model?: string
  download_url?: string
  file_size?: number
  trained_words: string[]
  files?: ModelFile[]
  published_at?: string
}

interface CivitaiModel {
  id: number
  name: string
  description?: string
  type: string
  nsfw: boolean
  tags: string[]
  creator?: string
  stats: {
    downloadCount?: number
    favoriteCount?: number
    commentCount?: number
    ratingCount?: number
    rating?: number
    thumbsUpCount?: number
  }
  versions: ModelVersion[]
  previews: ModelPreview[]
}

interface ModelDetail {
  id: number
  name: string
  description?: string
  type: string
  nsfw: boolean
  tags: string[]
  creator?: string
  trained_words: string[]
  base_model?: string
  versions: ModelVersion[]
  previews: ModelPreview[]
  stats: Record<string, any>
  download_count?: number
  rating?: number
  rating_count?: number
  published_at?: string
  hash_autov2?: string
  civitai_air?: string
  example_params?: Record<string, any>
}

interface Toast {
  id: string
  type: 'success' | 'error' | 'info'
  message: string
  details?: string
}

const MODEL_TYPES = [
  { value: '', label: 'All Types' },
  { value: 'LORA', label: 'LoRA' },
  { value: 'Checkpoint', label: 'Checkpoint' },
  { value: 'TextualInversion', label: 'Embedding' },
  { value: 'VAE', label: 'VAE' },
  { value: 'Controlnet', label: 'ControlNet' },
  { value: 'Upscaler', label: 'Upscaler' },
]

// Card widths for zoom - fixed sizes like Civitai
const CARD_WIDTHS = {
  sm: 220,
  md: 300,
  lg: 380,
}

type CardSize = keyof typeof CARD_WIDTHS

export function BrowsePage() {
  const queryClient = useQueryClient()

  const [searchQuery, setSearchQuery] = useState('')
  const [activeSearch, setActiveSearch] = useState('')
  const [selectedType, setSelectedType] = useState('')
  const [modelTypes, setModelTypes] = useState<string[]>([])  // Multi-select model types
  const [includeNsfw] = useState(true)

  // Phase 5: Search provider and filters
  const [searchProvider, setSearchProvider] = useState<SearchProvider>(() => {
    // Try to restore from localStorage
    if (typeof window !== 'undefined') {
      const saved = localStorage.getItem('synapse-search-provider')
      if (saved && ['rest', 'archive', 'trpc'].includes(saved)) {
        if (isProviderAvailable(saved as SearchProvider)) {
          return saved as SearchProvider
        }
      }
    }
    return getDefaultProvider()
  })
  const [sortBy, setSortBy] = useState<SortOption>('Most Downloaded')
  const [period, setPeriod] = useState<PeriodOption>('AllTime')
  const [baseModel, setBaseModel] = useState<string>('')

  // Persist provider choice
  useEffect(() => {
    localStorage.setItem('synapse-search-provider', searchProvider)
  }, [searchProvider])

  const [selectedModel, setSelectedModel] = useState<number | null>(null)
  const [toasts, setToasts] = useState<Toast[]>([])

  const [fullscreenIndex, setFullscreenIndex] = useState<number>(-1)
  const isFullscreenOpen = fullscreenIndex >= 0

  // Import Wizard state
  const [showImportWizard, setShowImportWizard] = useState(false)
  const [importWizardLoading, setImportWizardLoading] = useState(false)

  const [cardSize, setCardSize] = useState<CardSize>('md')

  // CRITICAL: Pagination state for Load More
  const [allModels, setAllModels] = useState<CivitaiModel[]>([])
  const [currentCursor, setCurrentCursor] = useState<string | undefined>()
  const [nextCursor, setNextCursor] = useState<string | undefined>()
  const isLoadingMore = useRef(false)

  // Toast functions
  const addToast = useCallback((type: Toast['type'], message: string, details?: string) => {
    const id = Math.random().toString(36).slice(2)
    console.log(`[Toast] ${type.toUpperCase()}: ${message}`, details || '')
    setToasts(prev => [...prev, { id, type, message, details }])
    setTimeout(() => setToasts(prev => prev.filter(t => t.id !== id)), 8000)
  }, [])

  const removeToast = (id: string) => setToasts(prev => prev.filter(t => t.id !== id))

  // Check if search is a special query
  const isSpecialQuery = activeSearch.startsWith('tag:') || activeSearch.startsWith('url:') || activeSearch.startsWith('https://')

  // Combine selectedType (dropdown) with modelTypes (chips) for search
  const effectiveModelTypes = [
    ...(selectedType ? [selectedType] : []),
    ...modelTypes.filter(t => t !== selectedType), // Avoid duplicates
  ]

  // Phase 5: Search query with adapter pattern
  const { data: searchResults, isLoading, error, isFetching } = useQuery({
    queryKey: [
      'civitai-search',
      activeSearch,
      selectedType,
      modelTypes,
      searchProvider,
      sortBy,
      period,
      baseModel,
      currentCursor,
    ],
    queryFn: async ({ signal }) => {
      // Get the adapter for current provider
      let adapter = getAdapter(searchProvider)

      // Fallback if tRPC not available
      if (!adapter.isAvailable() && searchProvider === 'trpc') {
        console.warn('[BrowsePage] tRPC bridge not available, falling back to REST')
        adapter = getAdapter('rest')
      }

      // For special queries (tag:, url:, https://), always use REST
      if (isSpecialQuery) {
        adapter = getAdapter('rest')
      }

      // CivArchive requires a search query
      if (searchProvider === 'archive' && !activeSearch) {
        return { items: [], next_cursor: undefined }
      }

      const result = await adapter.search(
        {
          query: activeSearch || undefined,
          types: effectiveModelTypes.length > 0 ? effectiveModelTypes : undefined,
          baseModels: baseModel ? [baseModel] : undefined,
          sort: sortBy,
          period,
          nsfw: includeNsfw,
          limit: 20,
          cursor: currentCursor,
        },
        signal
      )

      // Transform to expected format
      return {
        items: result.items,
        next_cursor: result.nextCursor,
      }
    },
    enabled: true,
    staleTime: 5 * 60 * 1000,
    retry: 2,
  })

  // CRITICAL: Handle search results for pagination
  useEffect(() => {
    if (searchResults) {
      if (isLoadingMore.current) {
        // Append to existing results (Load More)
        setAllModels(prev => [...prev, ...(searchResults.items || [])])
        isLoadingMore.current = false
      } else {
        // Replace with new results (new search)
        setAllModels(searchResults.items || [])
      }
      // Save next cursor for Load More
      setNextCursor(searchResults.next_cursor)
    }
  }, [searchResults])

  // Model detail query - uses adapter pattern (tRPC bridge when available)
  const { data: modelDetail, isLoading: isLoadingDetail } = useQuery<ModelDetail>({
    queryKey: ['civitai-model', selectedModel, searchProvider],
    queryFn: async () => {
      // Get adapter for current provider
      let adapter = getAdapter(searchProvider)

      // If adapter has getModelDetail, use it (tRPC, REST)
      // Otherwise fall back to REST (Archive doesn't support model fetch)
      if (!adapter.getModelDetail) {
        adapter = getAdapter('rest')
      }

      return adapter.getModelDetail!(selectedModel!)
    },
    enabled: !!selectedModel,
    staleTime: 5 * 60 * 1000, // Cache for 5 minutes
    retry: 2, // Limit retries to avoid long waits
  })

  // Handlers
  const handleSearch = (e: React.FormEvent) => {
    e.preventDefault()
    // Reset pagination state on new search
    isLoadingMore.current = false
    setAllModels([])
    setCurrentCursor(undefined)
    setNextCursor(undefined)
    setActiveSearch(searchQuery)
  }

  // Load More handler
  const handleLoadMore = () => {
    if (nextCursor && !isFetching) {
      isLoadingMore.current = true
      setCurrentCursor(nextCursor)
    }
  }

  const copyToClipboard = (text: string) => {
    navigator.clipboard.writeText(text)
    addToast('info', 'Copied to clipboard')
  }

  // Format helpers
  const formatNumber = (n?: number) => {
    if (!n) return '0'
    if (n >= 1000000) return `${(n / 1000000).toFixed(1)}M`
    if (n >= 1000) return `${(n / 1000).toFixed(1)}K`
    return n.toString()
  }

  const formatSize = (bytes?: number) => {
    if (!bytes) return ''
    const gb = bytes / (1024 * 1024 * 1024)
    if (gb >= 1) return `${gb.toFixed(1)} GB`
    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
  }

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

  // CRITICAL: Helper to get NSFW status
  const getPreviewNsfw = (model: CivitaiModel): boolean => {
    return model.nsfw || model.previews[0]?.nsfw || false
  }

  return (
    <div className="space-y-6">
      {/* Toast notifications */}
      <div className="fixed top-4 right-4 z-[100] space-y-2">
        {toasts.map(toast => (
          <div
            key={toast.id}
            className={clsx(
              'flex items-start gap-3 px-4 py-3 rounded-xl shadow-2xl min-w-[320px] max-w-[480px]',
              'animate-in slide-in-from-right duration-300',
              toast.type === 'success' && 'bg-green-600 text-white',
              toast.type === 'error' && 'bg-red-600 text-white',
              toast.type === 'info' && 'bg-blue-600 text-white',
            )}
          >
            {toast.type === 'success' && <CheckCircle className="w-5 h-5 flex-shrink-0 mt-0.5" />}
            {toast.type === 'error' && <AlertCircle className="w-5 h-5 flex-shrink-0 mt-0.5" />}
            {toast.type === 'info' && <Info className="w-5 h-5 flex-shrink-0 mt-0.5" />}
            <div className="flex-1 min-w-0">
              <p className="text-sm font-medium">{toast.message}</p>
              {toast.details && <p className="text-xs mt-1 opacity-90 break-words font-mono">{toast.details}</p>}
            </div>
            <button onClick={() => removeToast(toast.id)} className="text-white/70 hover:text-white">
              <X className="w-4 h-4" />
            </button>
          </div>
        ))}
      </div>

      {/* Fullscreen media viewer */}
      {modelDetail && (
        <FullscreenMediaViewer
          items={modelDetail.previews.map(p => ({
            url: p.url,
            type: p.media_type === 'video' ? 'video' : 'image',
            thumbnailUrl: p.thumbnail_url,
            nsfw: p.nsfw,
            width: p.width,
            height: p.height,
            meta: p.meta
          }))}
          initialIndex={fullscreenIndex}
          isOpen={isFullscreenOpen}
          onClose={() => setFullscreenIndex(-1)}
          onIndexChange={setFullscreenIndex}
        />
      )}

      {/* Import Wizard Modal */}
      {modelDetail && (
        <ImportWizardModal
          isOpen={showImportWizard}
          onClose={() => setShowImportWizard(false)}
          modelName={modelDetail.name}
          modelDescription={modelDetail.description}
          versions={modelDetail.versions.map(v => ({
            id: v.id,
            name: v.name,
            baseModel: v.base_model,
            createdAt: v.published_at,
            files: v.files?.map(f => ({
              id: f.id,
              name: f.name,
              sizeKB: f.size_kb,
              primary: true,
            })) || [],
            images: modelDetail.previews.map(p => ({
              url: p.url,
              nsfw: p.nsfw,
              width: p.width,
              height: p.height,
              type: p.media_type as 'image' | 'video' | undefined,
              meta: p.meta,
            })),
          }))}
          isLoading={importWizardLoading}
          onImport={async (selectedVersionIds, options, thumbnailUrl, customPackName) => {
            setImportWizardLoading(true)
            try {
              const res = await fetch('/api/packs/import', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                  url: `https://civitai.com/models/${modelDetail.id}`,
                  version_ids: selectedVersionIds,
                  download_images: options.downloadImages,
                  download_videos: options.downloadVideos,
                  include_nsfw: options.includeNsfw,
                  download_from_all_versions: options.downloadFromAllVersions,
                  thumbnail_url: thumbnailUrl,
                  pack_name: customPackName,  // Custom pack name if user edited it
                }),
              })
              if (!res.ok) {
                const err = await res.json()
                throw new Error(err.detail || 'Import failed')
              }
              const data = await res.json()
              addToast('success', `Successfully imported '${data.pack_name}'`)
              queryClient.invalidateQueries({ queryKey: ['packs'] })
              setShowImportWizard(false)
              setSelectedModel(null)
            } catch (error) {
              addToast('error', 'Import failed', (error as Error).message)
            } finally {
              setImportWizardLoading(false)
            }
          }}
        />
      )}

      {/* Header with zoom */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-text-primary">Browse Civitai</h1>
          <p className="text-text-muted mt-1">
            Search and import models. Use <code className="text-synapse px-1 py-0.5 bg-synapse/10 rounded">tag:</code> for tags.
          </p>
        </div>
        <div className="flex items-center gap-3">
          {/* Zoom controls */}
          <div className="flex items-center gap-1 bg-slate-dark/80 backdrop-blur rounded-xl p-1 border border-slate-mid/50">
            <button
              onClick={zoomOut}
              disabled={cardSize === 'sm'}
              className="p-2 rounded-lg hover:bg-slate-mid disabled:opacity-30 disabled:cursor-not-allowed transition-colors"
              title="Smaller cards"
            >
              <ZoomOut className="w-4 h-4 text-text-secondary" />
            </button>
            <div className="w-px h-4 bg-slate-mid" />
            <button
              onClick={zoomIn}
              disabled={cardSize === 'lg'}
              className="p-2 rounded-lg hover:bg-slate-mid disabled:opacity-30 disabled:cursor-not-allowed transition-colors"
              title="Larger cards"
            >
              <ZoomIn className="w-4 h-4 text-text-secondary" />
            </button>
          </div>
        </div>
      </div>

      {/* Search and filters */}
      <form onSubmit={handleSearch} className="flex gap-4">
        <div className="relative flex-1">
          <Search className="absolute left-4 top-1/2 -translate-y-1/2 w-5 h-5 text-text-muted" />
          <input
            type="text"
            value={searchQuery}
            onChange={e => setSearchQuery(e.target.value)}
            placeholder="Search models... (tag:anime, url:civitai.com/...)"
            className="w-full bg-slate-dark border border-slate-mid rounded-xl pl-12 pr-4 py-3 text-text-primary placeholder-text-muted focus:outline-none focus:ring-2 focus:ring-synapse"
          />
        </div>
        <select
          value={selectedType}
          onChange={e => {
            setSelectedType(e.target.value)
            // Reset pagination on type change
            isLoadingMore.current = false
            setAllModels([])
            setCurrentCursor(undefined)
            setNextCursor(undefined)
          }}
          className="bg-slate-dark border border-slate-mid rounded-xl px-4 py-3 text-text-primary focus:outline-none focus:ring-2 focus:ring-synapse"
        >
          {MODEL_TYPES.map(t => (
            <option key={t.value} value={t.value}>{t.label}</option>
          ))}
        </select>
        <Button type="submit" disabled={isLoading && !isFetching}>
          {isLoading && !isFetching ? <Loader2 className="w-4 h-4 animate-spin" /> : 'Search'}
        </Button>
      </form>

      {/* Phase 5: Search Filters - Floating Chips */}
      {!isSpecialQuery && (
        <SearchFilters
          provider={searchProvider}
          onProviderChange={(provider) => {
            setSearchProvider(provider)
            // Reset on provider change
            isLoadingMore.current = false
            setAllModels([])
            setCurrentCursor(undefined)
            setNextCursor(undefined)
          }}
          sortBy={sortBy}
          onSortChange={(sort) => {
            setSortBy(sort)
            // Reset on sort change
            isLoadingMore.current = false
            setAllModels([])
            setCurrentCursor(undefined)
            setNextCursor(undefined)
          }}
          period={period}
          onPeriodChange={(p) => {
            setPeriod(p)
            // Reset on period change
            isLoadingMore.current = false
            setAllModels([])
            setCurrentCursor(undefined)
            setNextCursor(undefined)
          }}
          baseModel={baseModel}
          onBaseModelChange={(model) => {
            setBaseModel(model)
            // Reset on base model change
            isLoadingMore.current = false
            setAllModels([])
            setCurrentCursor(undefined)
            setNextCursor(undefined)
          }}
          modelTypes={modelTypes}
          onModelTypesChange={(types) => {
            setModelTypes(types)
            // Reset on model types change
            isLoadingMore.current = false
            setAllModels([])
            setCurrentCursor(undefined)
            setNextCursor(undefined)
          }}
          isLoading={isFetching}
          isError={!!error}
        />
      )}

      {/* Error display */}
      {error && (
        <div className="bg-red-900/20 border border-red-500/50 rounded-xl p-4 flex items-center gap-3">
          <AlertCircle className="w-5 h-5 text-red-500 flex-shrink-0" />
          <span className="text-red-400">{(error as Error).message}</span>
        </div>
      )}

      {/* Premium Loading Animation - Breathing Orb */}
      {isLoading && allModels.length === 0 && !isLoadingMore.current && (
        <BreathingOrb
          size="lg"
          text="Searching models..."
          subtext={`Connecting to ${searchProvider === 'trpc' ? 'tRPC' : searchProvider === 'archive' ? 'CivArchive' : 'Civitai'}`}
          className="py-16"
        />
      )}

      {/* Results grid */}
      {/* Results grid */}
      <div
        className="flex flex-wrap gap-4"
        style={{ '--card-width': `${cardWidth}px` } as React.CSSProperties}
      >
        {allModels.map(model => (
          <div
            key={model.id}
            onClick={() => setSelectedModel(model.id)}
            className="group cursor-pointer"
            style={{ width: cardWidth }}
          >
            {/* Card */}
            <div className="relative aspect-[3/4] rounded-2xl overflow-hidden bg-slate-dark">
              {/* Preview with proper NSFW handling - combines model.nsfw AND preview.nsfw */}
              <MediaPreview
                src={model.previews[0]?.url || ''}
                type={model.previews[0]?.media_type}
                thumbnailSrc={model.previews[0]?.thumbnail_url}
                nsfw={getPreviewNsfw(model)}
                aspectRatio="portrait"
                className="w-full h-full"
                autoPlay={true}
              />

              {/* Gradient overlay */}
              <div className="absolute inset-0 bg-gradient-to-t from-black/90 via-black/20 to-transparent pointer-events-none" />

              {/* Content overlay */}
              <div className="absolute bottom-0 left-0 right-0 p-3 space-y-2">
                <h3 className="font-semibold text-white text-sm leading-tight line-clamp-2 group-hover:text-synapse transition-colors">
                  {model.name}
                </h3>

                <div className="flex items-center gap-2 text-xs text-white/70">
                  <span className="px-1.5 py-0.5 bg-white/20 rounded text-white/90">{model.type}</span>
                  {model.creator && (
                    <span className="flex items-center gap-1 truncate">
                      <User className="w-3 h-3" />
                      {model.creator}
                    </span>
                  )}
                </div>

                <div className="flex items-center gap-3 text-xs text-white/60">
                  <span className="flex items-center gap-1">
                    <Download className="w-3 h-3" />
                    {formatNumber(model.stats?.downloadCount)}
                  </span>
                  {model.stats?.thumbsUpCount != null && (
                    <span className="flex items-center gap-0.5">
                      <ThumbsUp className="w-3 h-3" />
                      {model.stats?.thumbsUpCount || Math.round((model.stats?.rating || 0) * 10)}
                    </span>
                  )}
                </div>
              </div>
            </div>
          </div>
        ))}
      </div>

      {/* Loading indicator for Load More */}
      {isFetching && isLoadingMore.current && (
        <BreathingOrb size="sm" className="py-8" />
      )}

      {/* CRITICAL: Load More button - must be visible when there's more data */}
      {nextCursor && !isFetching && allModels.length > 0 && (
        <div className="flex justify-center pt-4 pb-8">
          <Button
            onClick={handleLoadMore}
            variant="secondary"
            className="px-8 py-3"
          >
            Load More ({allModels.length} loaded)
          </Button>
        </div>
      )}

      {/* Empty state */}
      {!isLoading && !isFetching && allModels.length === 0 && activeSearch && (
        <div className="text-center py-12 text-text-muted">
          No models found for "{activeSearch}"
        </div>
      )}

      {/* Model Detail Modal */}
      {selectedModel && (
        <div
          className="fixed inset-0 bg-black/80 backdrop-blur-sm flex items-center justify-center z-50 p-4"
          onClick={() => setSelectedModel(null)}
        >
          <div
            className="bg-slate-deep border border-slate-mid rounded-2xl max-w-5xl w-full max-h-[90vh] overflow-hidden flex flex-col"
            onClick={e => e.stopPropagation()}
          >
            {isLoadingDetail ? (
              <BreathingOrb size="md" text="Loading model..." className="py-20" />
            ) : modelDetail ? (
              <>
                {/* Modal Header */}
                <div className="bg-slate-dark/95 backdrop-blur-xl border-b border-slate-mid p-4 flex items-start justify-between gap-4 flex-shrink-0">
                  <div className="min-w-0 flex-1">
                    <h2 className="text-xl font-bold text-text-primary break-words">{modelDetail.name}</h2>
                    <div className="flex items-center gap-3 mt-1 text-sm text-text-muted flex-wrap">
                      <span className="px-2 py-0.5 bg-synapse/20 text-synapse rounded-lg font-medium">{modelDetail.type}</span>
                      {modelDetail.base_model && (
                        <span className="px-2 py-0.5 bg-slate-mid rounded-lg">{modelDetail.base_model}</span>
                      )}
                      {modelDetail.creator && (
                        <span className="flex items-center gap-1">
                          <User className="w-3 h-3" />
                          {modelDetail.creator}
                        </span>
                      )}
                    </div>
                  </div>
                  <div className="flex items-center gap-3 flex-shrink-0">
                    {/* Main Import Button - Opens Wizard */}
                    <Button
                      onClick={() => setShowImportWizard(true)}
                      className="bg-gradient-to-r from-synapse to-pulse hover:shadow-lg hover:shadow-synapse/25 whitespace-nowrap"
                    >
                      <Download className="w-4 h-4 mr-2" />
                      Import to Pack...
                    </Button>
                    <button
                      onClick={() => setSelectedModel(null)}
                      className="p-2 hover:bg-slate-mid rounded-xl text-text-muted hover:text-text-primary transition-colors"
                    >
                      <X className="w-5 h-5" />
                    </button>
                  </div>
                </div>

                {/* Modal Content - Scrollable */}
                <div className="p-6 space-y-6 overflow-y-auto flex-1">
                  {/* Preview Gallery */}
                  <div className="space-y-3">
                    <h3 className="text-sm font-semibold text-text-primary">
                      Preview Images ({modelDetail.previews.length})
                    </h3>
                    <div className="grid grid-cols-6 gap-3 max-h-[360px] overflow-y-auto p-1">
                      {modelDetail.previews.map((preview, idx) => (
                        <MediaPreview
                          key={idx}
                          src={preview.url}
                          type={preview.media_type}
                          thumbnailSrc={preview.thumbnail_url}
                          nsfw={preview.nsfw}
                          aspectRatio="portrait"
                          className="cursor-pointer hover:ring-2 ring-synapse"
                          autoPlay={true}
                          onClick={() => setFullscreenIndex(idx)}
                        />
                      ))}
                    </div>
                  </div>

                  {/* Usage Tips */}
                  <div className="bg-gradient-to-r from-synapse/10 to-pulse/10 border border-synapse/30 rounded-xl p-4">
                    <h3 className="text-sm font-semibold text-synapse mb-3 flex items-center gap-2">
                      <Info className="w-4 h-4" />
                      Usage Tips
                    </h3>
                    <div className="grid grid-cols-3 md:grid-cols-6 gap-3">
                      {modelDetail.example_params?.clip_skip != null && (
                        <div className="bg-slate-dark/80 rounded-xl p-3 text-center">
                          <span className="text-text-muted block text-xs mb-1">Clip Skip</span>
                          <span className="text-synapse font-bold text-xl">{modelDetail.example_params.clip_skip}</span>
                        </div>
                      )}
                      {modelDetail.type === 'LORA' && (
                        <div className="bg-slate-dark/80 rounded-xl p-3 text-center">
                          <span className="text-text-muted block text-xs mb-1">Strength</span>
                          <span className="text-synapse font-bold text-xl">1.0</span>
                        </div>
                      )}
                      {modelDetail.example_params?.cfg_scale != null && (
                        <div className="bg-slate-dark/80 rounded-xl p-3 text-center">
                          <span className="text-text-muted block text-xs mb-1">CFG Scale</span>
                          <span className="text-synapse font-bold text-xl">{modelDetail.example_params.cfg_scale}</span>
                        </div>
                      )}
                      {modelDetail.example_params?.steps != null && (
                        <div className="bg-slate-dark/80 rounded-xl p-3 text-center">
                          <span className="text-text-muted block text-xs mb-1">Steps</span>
                          <span className="text-synapse font-bold text-xl">{modelDetail.example_params.steps}</span>
                        </div>
                      )}
                      {modelDetail.example_params?.sampler != null && (
                        <div className="bg-slate-dark/80 rounded-xl p-3 text-center col-span-2">
                          <span className="text-text-muted block text-xs mb-1">Sampler</span>
                          <span className="text-synapse font-bold text-sm">{modelDetail.example_params.sampler}</span>
                        </div>
                      )}
                    </div>
                  </div>

                  {/* Trigger Words */}
                  {modelDetail.trained_words?.length > 0 && (
                    <div className="space-y-2">
                      <h3 className="text-sm font-semibold text-text-primary">Trigger Words</h3>
                      <div className="flex flex-wrap gap-2">
                        {modelDetail.trained_words.map((word, idx) => (
                          <button
                            key={idx}
                            onClick={() => copyToClipboard(word)}
                            className="px-3 py-1.5 bg-synapse/20 text-synapse rounded-lg text-sm hover:bg-synapse/30 transition-colors flex items-center gap-1.5"
                          >
                            <Copy className="w-3 h-3" />
                            {word}
                          </button>
                        ))}
                      </div>
                    </div>
                  )}

                  {/* Versions */}
                  {modelDetail.versions?.length > 0 && (
                    <div className="space-y-3">
                      <h3 className="text-sm font-semibold text-text-primary">
                        Versions ({modelDetail.versions.length})
                      </h3>
                      <div className="space-y-2">
                        {modelDetail.versions.slice(0, 5).map((version, idx) => (
                          <div
                            key={version.id}
                            className={clsx(
                              'p-3 rounded-xl border',
                              idx === 0 ? 'bg-synapse/10 border-synapse/30' : 'bg-slate-dark border-slate-mid'
                            )}
                          >
                            <div className="flex items-center justify-between">
                              <div>
                                <span className="font-medium text-text-primary">{version.name}</span>
                                {idx === 0 && (
                                  <span className="ml-2 text-xs bg-synapse/30 text-synapse px-2 py-0.5 rounded">Latest</span>
                                )}
                                <div className="text-xs text-text-muted mt-1 flex items-center gap-3">
                                  {version.base_model && <span>{version.base_model}</span>}
                                  {version.file_size && <span>{formatSize(version.file_size)}</span>}
                                </div>
                              </div>
                              <Button
                                size="sm"
                                variant="secondary"
                                onClick={(e) => {
                                  e.stopPropagation()
                                  window.open(`https://civitai.com/models/${modelDetail.id}?modelVersionId=${version.id}`, '_blank')
                                }}
                              >
                                <ExternalLink className="w-4 h-4" />
                              </Button>
                            </div>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}

                  {/* Description */}
                  {modelDetail.description && (
                    <div className="space-y-2">
                      <h3 className="text-sm font-semibold text-text-primary">Description</h3>
                      <div
                        className="prose prose-invert prose-sm max-w-none text-text-secondary"
                        dangerouslySetInnerHTML={{ __html: modelDetail.description }}
                      />
                    </div>
                  )}

                  {/* Tags */}
                  {modelDetail.tags?.length > 0 && (
                    <div className="space-y-2">
                      <h3 className="text-sm font-semibold text-text-primary">Tags</h3>
                      <div className="flex flex-wrap gap-2">
                        {modelDetail.tags.map((tag, idx) => (
                          <span
                            key={idx}
                            className="px-2 py-1 bg-slate-mid rounded-lg text-xs text-text-secondary hover:bg-slate-light cursor-pointer transition-colors"
                            onClick={() => {
                              setSearchQuery(`tag:${tag}`)
                              setSelectedModel(null)
                            }}
                          >
                            {tag}
                          </span>
                        ))}
                      </div>
                    </div>
                  )}

                  {/* Stats */}
                  <div className="flex items-center gap-4 pt-4 border-t border-slate-mid text-sm text-text-muted">
                    <span className="flex items-center gap-1">
                      <Download className="w-4 h-4" />
                      {formatNumber(modelDetail.download_count)} downloads
                    </span>
                    {modelDetail.rating != null && (
                      <span className="flex items-center gap-1">
                        <Heart className="w-4 h-4" />
                        {modelDetail.rating.toFixed(1)} ({formatNumber(modelDetail.rating_count)} ratings)
                      </span>
                    )}
                    <a
                      href={`https://civitai.com/models/${modelDetail.id}`}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="flex items-center gap-1 text-synapse hover:underline ml-auto"
                    >
                      <ExternalLink className="w-4 h-4" />
                      View on Civitai
                    </a>
                  </div>
                </div>
              </>
            ) : (
              <div className="p-6 text-center text-text-muted">
                Model not found
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  )
}
