import { useState, useEffect, useRef, useCallback } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import {
  Search, Download, X, ExternalLink,
  User, Heart, Loader2, AlertCircle, CheckCircle, Info, Copy,
  ZoomIn, ZoomOut, Maximize2, MessageSquare, Link2, ThumbsUp
} from 'lucide-react'
import { Button } from '@/components/ui/Button'
import { clsx } from 'clsx'
import { useSettingsStore } from '@/stores/settingsStore'

interface ModelPreview {
  url: string
  nsfw: boolean
  width?: number
  height?: number
  meta?: Record<string, any>
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
  const { nsfwBlurEnabled } = useSettingsStore()

  const [searchQuery, setSearchQuery] = useState('')
  const [activeSearch, setActiveSearch] = useState('')
  const [selectedType, setSelectedType] = useState('')
  const [includeNsfw] = useState(true)
  const [useCivArchive, setUseCivArchive] = useState(false)  // CivArchive toggle
  const [selectedModel, setSelectedModel] = useState<number | null>(null)
  const [toasts, setToasts] = useState<Toast[]>([])
  const [fullscreenImage, setFullscreenImage] = useState<string | null>(null)
  const [cardSize, setCardSize] = useState<CardSize>('md')

  // Pagination state
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

  // Check if search is a special query (tag: or url:) - CivArchive only for regular queries
  const isSpecialQuery = activeSearch.startsWith('tag:') || activeSearch.startsWith('url:') || activeSearch.startsWith('https://')

  // Search query with longer timeout
  const { data: searchResults, isLoading, error, isFetching } = useQuery({
    queryKey: ['civitai-search', activeSearch, selectedType, includeNsfw, currentCursor, useCivArchive],
    queryFn: async () => {
      // Use CivArchive for regular queries when toggle is on
      if (useCivArchive && activeSearch && !isSpecialQuery) {
        console.log('[BrowsePage] Using CivArchive search for:', activeSearch)

        const params = new URLSearchParams()
        params.append('query', activeSearch)
        params.append('limit', '20')

        const controller = new AbortController()
        const timeoutId = setTimeout(() => controller.abort(), 90000) // 90s timeout for CivArchive

        try {
          const res = await fetch(`/api/browse/search-civarchive?${params}`, {
            signal: controller.signal
          })
          clearTimeout(timeoutId)

          if (!res.ok) {
            const errData = await res.json().catch(() => ({}))
            throw new Error(errData.detail || 'CivArchive search failed')
          }

          const civarchiveData = await res.json()
          console.log('[BrowsePage] CivArchive results:', civarchiveData.results?.length)

          // Transform CivArchive results to CivitaiModel format
          const transformedItems = (civarchiveData.results || []).map((r: any) => ({
            id: r.model_id,
            name: r.model_name,
            type: r.model_type || 'Unknown',
            nsfw: r.nsfw || false,
            tags: [],
            creator: r.creator,
            stats: {
              downloadCount: r.download_count,
              rating: r.rating,
            },
            versions: [{
              id: r.version_id,
              name: r.version_name || 'Default',
              base_model: r.base_model,
              download_url: r.download_url,
              file_size: r.file_size,
              trained_words: [],
              files: r.file_name ? [{
                id: 0,
                name: r.file_name,
                size_kb: r.file_size ? r.file_size / 1024 : undefined,
                download_url: r.download_url,
              }] : [],
            }],
            // Include preview from CivArchive response
            previews: r.preview_url ? [{
              url: r.preview_url,
              nsfw: r.nsfw || false,
            }] : [],
          }))

          return {
            items: transformedItems,
            next_cursor: null,  // CivArchive doesn't support pagination yet
          }
        } catch (err: any) {
          if (err.name === 'AbortError') {
            throw new Error('CivArchive request timeout - try again')
          }
          throw err
        }
      }

      // Standard Civitai search
      const params = new URLSearchParams()
      if (activeSearch) params.append('query', activeSearch)
      if (selectedType) params.append('types', selectedType)
      if (includeNsfw) params.append('nsfw', 'true')
      if (currentCursor) params.append('cursor', currentCursor)
      params.append('limit', '20')

      const controller = new AbortController()
      const timeoutId = setTimeout(() => controller.abort(), 30000) // 30s timeout

      try {
        const res = await fetch(`/api/browse/search?${params}`, {
          signal: controller.signal
        })
        clearTimeout(timeoutId)

        if (!res.ok) {
          const errData = await res.json().catch(() => ({}))
          throw new Error(errData.detail || 'Search failed')
        }
        return res.json()
      } catch (err: any) {
        if (err.name === 'AbortError') {
          throw new Error('Request timeout - try again')
        }
        throw err
      }
    },
    enabled: !!activeSearch || activeSearch === '',
    staleTime: 5 * 60 * 1000,
    retry: 2,
  })

  // Handle search results
  useEffect(() => {
    if (searchResults) {
      if (isLoadingMore.current) {
        setAllModels(prev => [...prev, ...(searchResults.items || [])])
        isLoadingMore.current = false
      } else {
        setAllModels(searchResults.items || [])
      }
      setNextCursor(searchResults.next_cursor)
    }
  }, [searchResults])

  // Model detail query
  const { data: modelDetail, isLoading: isLoadingDetail } = useQuery<ModelDetail>({
    queryKey: ['civitai-model', selectedModel],
    queryFn: async () => {
      const res = await fetch(`/api/browse/model/${selectedModel}`)
      if (!res.ok) {
        const errData = await res.json().catch(() => ({}))
        throw new Error(errData.detail || 'Failed to fetch model')
      }
      return res.json()
    },
    enabled: !!selectedModel,
  })

  // Import mutation
  const importMutation = useMutation({
    mutationFn: async (url: string) => {
      // V2 API endpoint
      const res = await fetch('/api/packs/import', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ url }),
      })
      const data = await res.json()
      if (!res.ok) throw new Error(data.detail || data.message || JSON.stringify(data))
      return data
    },
    onSuccess: (data) => {
      addToast('success', data.message || `Successfully imported '${data.pack_name}'`)
      queryClient.invalidateQueries({ queryKey: ['packs'] })
      setSelectedModel(null)
    },
    onError: (error: Error) => {
      addToast('error', 'Import failed', error.message)
    },
  })

  // Handlers
  const handleSearch = (e: React.FormEvent) => {
    e.preventDefault()
    isLoadingMore.current = false
    setAllModels([])
    setCurrentCursor(undefined)
    setNextCursor(undefined)
    setActiveSearch(searchQuery)
  }

  const handleLoadMore = () => {
    if (nextCursor && !isFetching) {
      isLoadingMore.current = true
      setCurrentCursor(nextCursor)
    }
  }

  const handleImport = (modelId: number) => {
    importMutation.mutate(`https://civitai.com/models/${modelId}`)
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

      {/* Header with zoom */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-text-primary">Browse Civitai</h1>
          <p className="text-text-muted mt-1">
            Search and import models. Use <code className="text-synapse px-1 py-0.5 bg-synapse/10 rounded">tag:</code> for tags.
          </p>
        </div>

        {/* Zoom controls */}
        <div className="flex items-center gap-1 bg-slate-dark/80 backdrop-blur rounded-xl p-1 border border-slate-mid/50">
          <button
            onClick={zoomOut}
            disabled={cardSize === 'sm'}
            className="p-2 rounded-lg hover:bg-slate-mid disabled:opacity-30 disabled:cursor-not-allowed transition-colors"
            title="Zoom out"
          >
            <ZoomOut className="w-4 h-4 text-text-secondary" />
          </button>
          <div className="w-px h-6 bg-slate-mid" />
          <button
            onClick={zoomIn}
            disabled={cardSize === 'lg'}
            className="p-2 rounded-lg hover:bg-slate-mid disabled:opacity-30 disabled:cursor-not-allowed transition-colors"
            title="Zoom in"
          >
            <ZoomIn className="w-4 h-4 text-text-secondary" />
          </button>
        </div>
      </div>

      {/* Search bar */}
      <form onSubmit={handleSearch} className="flex gap-4">
        <div className="flex-1 relative">
          <Search className="absolute left-4 top-1/2 -translate-y-1/2 w-5 h-5 text-text-muted" />
          <input
            type="text"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            placeholder="Search models, tag:anime, or paste Civitai URL..."
            className="w-full pl-12 pr-4 py-3 bg-slate-dark border border-slate-mid rounded-xl text-text-primary placeholder-text-muted focus:outline-none focus:border-synapse transition-colors"
          />
        </div>

        <select
          value={selectedType}
          onChange={(e) => setSelectedType(e.target.value)}
          className="px-4 py-3 bg-slate-dark border border-slate-mid rounded-xl text-text-primary focus:outline-none focus:border-synapse cursor-pointer"
        >
          {MODEL_TYPES.map(type => (
            <option key={type.value} value={type.value}>{type.label}</option>
          ))}
        </select>

        {/* CivArchive toggle - compact design matching NSFW toggle style */}
        <button
          type="button"
          onClick={() => setUseCivArchive(!useCivArchive)}
          className={clsx(
            "flex items-center gap-2 px-3 py-2.5 rounded-xl text-sm transition-all",
            useCivArchive
              ? "bg-synapse/20 text-synapse border border-synapse/50"
              : "bg-slate-dark text-text-muted border border-slate-mid hover:border-slate-light"
          )}
          title="Use CivArchive.com for better full-text search (slower but more accurate)"
        >
          <span className="font-medium">Archive</span>
          {/* Toggle switch */}
          <div className={clsx(
            "w-8 h-4 rounded-full relative transition-colors",
            useCivArchive ? "bg-synapse/40" : "bg-slate-mid"
          )}>
            <div className={clsx(
              "absolute top-0.5 w-3 h-3 rounded-full transition-all duration-200",
              useCivArchive
                ? "left-4 bg-synapse"
                : "left-0.5 bg-text-muted"
            )} />
          </div>
        </button>

        <Button type="submit" disabled={isLoading}>
          {isLoading && !isLoadingMore.current ? (
            <Loader2 className="w-5 h-5 animate-spin" />
          ) : (
            <Search className="w-5 h-5" />
          )}
          Search
        </Button>
      </form>

      {/* CivArchive info banner - only show when active */}
      {useCivArchive && (
        <div className="bg-synapse/10 border border-synapse/30 rounded-lg px-3 py-1.5 flex items-center gap-2 text-xs">
          <Info className="w-3 h-3 text-synapse flex-shrink-0" />
          <span className="text-text-muted">
            <span className="text-synapse font-medium">Archive search:</span> Better quality via civarchive.com. Slower but searches descriptions.
          </span>
        </div>
      )}

      {/* Error display */}
      {error && (
        <div className="bg-red-900/20 border border-red-500/50 rounded-xl p-4 flex items-center gap-3">
          <AlertCircle className="w-5 h-5 text-red-500 flex-shrink-0" />
          <span className="text-red-400">{(error as Error).message}</span>
        </div>
      )}

      {/* Results grid - CIVITAI STYLE: fixed width cards, flex wrap */}
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
            {/* Card - Civitai style: image fills card, content overlaid */}
            <div className="relative aspect-[3/4] rounded-2xl overflow-hidden bg-slate-dark">
              {/* Image with hover zoom */}
              {model.previews[0]?.url ? (
                <img
                  src={model.previews[0].url}
                  alt={model.name}
                  className={clsx(
                    "w-full h-full object-cover transition-all duration-500 ease-out",
                    "group-hover:scale-110",
                    nsfwBlurEnabled && model.nsfw && "blur-xl group-hover:blur-0"
                  )}
                  loading="lazy"
                />
              ) : (
                <div className="w-full h-full flex items-center justify-center text-text-muted bg-gradient-to-br from-slate-dark to-slate-mid">
                  <span className="text-sm">No Preview</span>
                </div>
              )}

              {/* NSFW overlay indicator */}
              {nsfwBlurEnabled && model.nsfw && (
                <div className="absolute inset-0 flex items-center justify-center bg-black/30 group-hover:opacity-0 transition-opacity duration-500 pointer-events-none z-10">
                  <span className="px-3 py-1.5 bg-red-500/80 backdrop-blur-sm rounded-lg text-sm text-white font-semibold">
                    NSFW
                  </span>
                </div>
              )}

              {/* Gradient overlay */}
              <div className="absolute inset-0 bg-gradient-to-t from-black/90 via-black/30 to-transparent pointer-events-none" />

              {/* Top left badges */}
              <div className="absolute top-3 left-3 flex gap-1.5">
                <span className="px-2 py-1 bg-black/60 backdrop-blur-sm rounded-lg text-xs text-white font-semibold">
                  {model.type}
                </span>
                {model.versions[0]?.base_model && (
                  <span className="px-2 py-1 bg-black/60 backdrop-blur-sm rounded-lg text-xs text-white/80">
                    {model.versions[0].base_model.replace('SD ', '').replace('SDXL ', 'XL ')}
                  </span>
                )}
              </div>

              {/* Top right icons */}
              <div className="absolute top-3 right-3 flex gap-1.5">
                <button
                  className="p-1.5 bg-white/90 hover:bg-white rounded-full transition-colors"
                  onClick={(e) => {
                    e.stopPropagation()
                    navigator.clipboard.writeText(`https://civitai.com/models/${model.id}`)
                    addToast('info', 'Link copied')
                  }}
                >
                  <Link2 className="w-4 h-4 text-slate-700" />
                </button>
              </div>

              {/* Bottom content */}
              <div className="absolute bottom-0 left-0 right-0 p-3 space-y-2">
                {/* Creator row */}
                {model.creator && (
                  <div className="flex items-center gap-2">
                    <div className="w-6 h-6 rounded-full bg-gradient-to-br from-synapse to-pulse flex items-center justify-center text-white text-xs font-bold">
                      {model.creator.charAt(0).toUpperCase()}
                    </div>
                    <span className="text-sm text-white/90 font-medium">{model.creator}</span>
                  </div>
                )}

                {/* Title */}
                <h3 className="font-bold text-white text-sm leading-tight line-clamp-2">
                  {model.name}
                </h3>

                {/* Stats row - exactly like Civitai */}
                <div className="flex items-center gap-3 text-xs text-white/70">
                  <span className="flex items-center gap-1">
                    <Download className="w-3.5 h-3.5" />
                    {formatNumber(model.stats?.downloadCount)}
                  </span>
                  <span className="flex items-center gap-1">
                    <MessageSquare className="w-3.5 h-3.5" />
                    {formatNumber(model.stats?.commentCount)}
                  </span>
                  <span className="flex items-center gap-1">
                    <Heart className="w-3.5 h-3.5" />
                    {formatNumber(model.stats?.favoriteCount)}
                  </span>
                  {(model.stats?.thumbsUpCount || model.stats?.rating) && (
                    <span className="flex items-center gap-1 ml-auto bg-white/20 px-2 py-0.5 rounded-md">
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

      {/* Loading indicator */}
      {isFetching && isLoadingMore.current && (
        <div className="flex justify-center py-8">
          <Loader2 className="w-8 h-8 animate-spin text-synapse" />
        </div>
      )}

      {/* Load More button */}
      {nextCursor && !isFetching && (
        <div className="flex justify-center pt-4">
          <Button onClick={handleLoadMore} variant="secondary" className="px-8">
            Load More ({allModels.length} loaded)
          </Button>
        </div>
      )}

      {/* Empty state */}
      {!isLoading && allModels.length === 0 && activeSearch && (
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
              <div className="flex items-center justify-center py-20">
                <Loader2 className="w-8 h-8 animate-spin text-synapse" />
              </div>
            ) : modelDetail ? (
              <>
                {/* Modal Header */}
                <div className="bg-slate-dark/95 backdrop-blur-xl border-b border-slate-mid p-4 flex items-center justify-between flex-shrink-0">
                  <div>
                    <h2 className="text-xl font-bold text-text-primary">{modelDetail.name}</h2>
                    <div className="flex items-center gap-3 mt-1 text-sm text-text-muted">
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
                  <button
                    onClick={() => setSelectedModel(null)}
                    className="p-2 hover:bg-slate-mid rounded-xl text-text-muted hover:text-text-primary transition-colors"
                  >
                    <X className="w-5 h-5" />
                  </button>
                </div>

                {/* Modal Content - Scrollable */}
                <div className="p-6 space-y-6 overflow-y-auto flex-1">
                  {/* Preview Gallery - 2 rows, ALL previews */}
                  <div className="space-y-3">
                    <h3 className="text-sm font-semibold text-text-primary">
                      Preview Images ({modelDetail.previews.length})
                    </h3>
                    <div className="grid grid-cols-6 gap-3 max-h-[360px] overflow-y-auto p-1">
                      {modelDetail.previews.map((preview, idx) => (
                        <div
                          key={idx}
                          className="aspect-[3/4] rounded-xl overflow-hidden bg-slate-dark cursor-pointer group relative"
                          onClick={() => setFullscreenImage(preview.url)}
                        >
                          <img
                            src={preview.url}
                            alt={`Preview ${idx + 1}`}
                            className={clsx(
                              "w-full h-full object-cover transition-all duration-300 group-hover:scale-105",
                              nsfwBlurEnabled && preview.nsfw && "blur-xl group-hover:blur-0"
                            )}
                            loading="lazy"
                          />
                          {/* NSFW overlay */}
                          {nsfwBlurEnabled && preview.nsfw && (
                            <div className="absolute inset-0 flex items-center justify-center bg-black/30 group-hover:opacity-0 transition-opacity duration-300 pointer-events-none z-10">
                              <span className="px-2 py-1 bg-red-500/80 backdrop-blur-sm rounded text-xs text-white font-semibold">
                                NSFW
                              </span>
                            </div>
                          )}
                          <div className="absolute inset-0 bg-black/0 group-hover:bg-black/40 transition-colors flex items-center justify-center z-20">
                            <Maximize2 className="w-8 h-8 text-white opacity-0 group-hover:opacity-100 transition-opacity drop-shadow-lg" />
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>

                  {/* Usage Tips / Parameters - CRITICAL SECTION */}
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
                          <span className="text-text-primary font-bold text-xl">{modelDetail.example_params.cfg_scale}</span>
                        </div>
                      )}
                      {modelDetail.example_params?.steps != null && (
                        <div className="bg-slate-dark/80 rounded-xl p-3 text-center">
                          <span className="text-text-muted block text-xs mb-1">Steps</span>
                          <span className="text-text-primary font-bold text-xl">{modelDetail.example_params.steps}</span>
                        </div>
                      )}
                      {modelDetail.example_params?.sampler && (
                        <div className="bg-slate-dark/80 rounded-xl p-3 text-center col-span-2">
                          <span className="text-text-muted block text-xs mb-1">Sampler</span>
                          <span className="text-text-primary font-medium text-sm">{modelDetail.example_params.sampler}</span>
                        </div>
                      )}
                    </div>
                    {!modelDetail.example_params?.clip_skip && !modelDetail.example_params?.cfg_scale && modelDetail.type !== 'LORA' && (
                      <p className="text-text-muted text-sm mt-3">No usage parameters available from example images.</p>
                    )}
                  </div>

                  {/* Description */}
                  {modelDetail.description && (
                    <div className="bg-slate-dark rounded-xl p-4">
                      <h3 className="text-sm font-semibold text-text-primary mb-3">Description</h3>
                      <div
                        className="prose prose-invert prose-sm max-w-none text-text-secondary [&_a]:text-synapse"
                        dangerouslySetInnerHTML={{ __html: modelDetail.description }}
                      />
                    </div>
                  )}

                  {/* Trigger Words */}
                  {modelDetail.trained_words?.length > 0 && (
                    <div className="bg-slate-dark rounded-xl p-4">
                      <h3 className="text-sm font-semibold text-text-primary mb-3">Trigger Words</h3>
                      <div className="flex flex-wrap gap-2">
                        {modelDetail.trained_words.map((word, idx) => (
                          <button
                            key={idx}
                            onClick={() => copyToClipboard(word)}
                            className="px-3 py-1.5 bg-synapse/20 text-synapse rounded-lg text-sm hover:bg-synapse/30 transition-colors flex items-center gap-2"
                          >
                            <code>{word}</code>
                            <Copy className="w-3 h-3" />
                          </button>
                        ))}
                      </div>
                    </div>
                  )}

                  {/* Model Info */}
                  <div className="bg-slate-dark rounded-xl p-4">
                    <h3 className="text-sm font-semibold text-text-primary mb-3">Model Info</h3>
                    <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-sm">
                      <div>
                        <span className="text-text-muted block">Type</span>
                        <span className="text-text-primary font-medium">{modelDetail.type}</span>
                      </div>
                      {modelDetail.base_model && (
                        <div>
                          <span className="text-text-muted block">Base Model</span>
                          <span className="text-text-primary font-medium">{modelDetail.base_model}</span>
                        </div>
                      )}
                      <div>
                        <span className="text-text-muted block">Downloads</span>
                        <span className="text-text-primary font-medium">{formatNumber(modelDetail.download_count)}</span>
                      </div>
                      {modelDetail.rating && (
                        <div>
                          <span className="text-text-muted block">Rating</span>
                          <span className="text-text-primary font-medium">⭐ {modelDetail.rating.toFixed(2)}</span>
                        </div>
                      )}
                    </div>
                  </div>

                  {/* Tags */}
                  {modelDetail.tags?.length > 0 && (
                    <div>
                      <h3 className="text-sm font-semibold text-text-primary mb-2">Tags</h3>
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

                  {/* Versions */}
                  {modelDetail.versions?.length > 0 && (
                    <div>
                      <h3 className="text-sm font-semibold text-text-primary mb-2">
                        Versions ({modelDetail.versions.length})
                      </h3>
                      <div className="space-y-2">
                        {modelDetail.versions.slice(0, 5).map((version, idx) => (
                          <div
                            key={version.id}
                            className={clsx(
                              'p-3 rounded-xl border',
                              idx === 0 ? 'bg-synapse/10 border-synapse/50' : 'bg-slate-dark border-slate-mid'
                            )}
                          >
                            <div className="flex items-center justify-between">
                              <div className="flex items-center gap-2">
                                <span className="font-medium text-text-primary">{version.name}</span>
                                {version.base_model && (
                                  <span className="text-xs text-text-muted px-2 py-0.5 bg-slate-mid rounded-lg">
                                    {version.base_model}
                                  </span>
                                )}
                                {idx === 0 && (
                                  <span className="px-2 py-0.5 bg-synapse text-white text-xs rounded-lg font-medium">
                                    Latest
                                  </span>
                                )}
                              </div>
                              {version.file_size && (
                                <span className="text-sm text-text-muted">{formatSize(version.file_size)}</span>
                              )}
                            </div>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}
                </div>

                {/* Actions - Fixed at bottom */}
                <div className="flex gap-3 p-4 border-t border-slate-mid bg-slate-dark/95 backdrop-blur-xl flex-shrink-0">
                  <Button
                    onClick={() => handleImport(modelDetail.id)}
                    disabled={importMutation.isPending}
                    className="flex-1"
                  >
                    {importMutation.isPending ? (
                      <Loader2 className="w-5 h-5 animate-spin" />
                    ) : (
                      <Download className="w-5 h-5" />
                    )}
                    Import to Synapse
                  </Button>
                  <Button
                    variant="secondary"
                    onClick={() => window.open(`https://civitai.com/models/${modelDetail.id}`, '_blank')}
                  >
                    <ExternalLink className="w-5 h-5" />
                    View on Civitai
                  </Button>
                </div>
              </>
            ) : null}
          </div>
        </div>
      )}
    </div>
  )
}
