import { useState, useEffect } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import {
  ArrowLeft, Download, Play, Trash2, ExternalLink, Tag,
  AlertTriangle, Check, Search, Loader2, X, Database,
  HardDrive, Globe, Package, Info, Copy, ChevronRight, ChevronDown, Edit3,
  FileJson, DownloadCloud, FolderOpen, Gauge, Timer,
  ArrowLeftRight, RotateCcw, Zap, ZoomIn, ZoomOut
} from 'lucide-react'
import { Button } from '@/components/ui/Button'
import { Card } from '@/components/ui/Card'
import { ProgressBar } from '@/components/ui/ProgressBar'
import { clsx } from 'clsx'

import { toast } from '@/stores/toastStore'
import { MediaPreview } from '@/components/ui/MediaPreview'
import { FullscreenMediaViewer } from '@/components/ui/FullscreenMediaViewer'
import { BreathingOrb } from '@/components/ui/BreathingOrb'
import { MediaType } from '@/lib/media'

// Download progress tracking
interface DownloadProgress {
  download_id: string
  pack_name: string
  asset_name: string
  filename: string
  status: string
  progress: number
  downloaded_bytes: number
  total_bytes: number
  speed_bps: number
  eta_seconds: number | null
  error: string | null
}

/**
 * Format bytes to human readable string
 */
function formatBytes(bytes: number | undefined | null): string {
  if (bytes === undefined || bytes === null || isNaN(bytes) || bytes === 0) return '0 B'
  const k = 1024
  const sizes = ['B', 'KB', 'MB', 'GB', 'TB']
  const i = Math.floor(Math.log(bytes) / Math.log(k))
  return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i]
}

/**
 * Format speed (bytes per second) to human readable
 */
function formatSpeed(bps: number | undefined | null): string {
  if (bps === undefined || bps === null || isNaN(bps) || bps === 0) return '--'
  return formatBytes(bps) + '/s'
}

/**
 * Format seconds to human readable time
 */
function formatEta(seconds: number | undefined | null): string {
  if (seconds === undefined || seconds === null || isNaN(seconds) || seconds <= 0) return '--'
  if (seconds < 60) return `${Math.round(seconds)}s`
  if (seconds < 3600) {
    const mins = Math.floor(seconds / 60)
    const secs = Math.round(seconds % 60)
    return `${mins}m ${secs}s`
  }
  const hours = Math.floor(seconds / 3600)
  const mins = Math.floor((seconds % 3600) / 60)
  return `${hours}h ${mins}m`
}

interface AssetInfo {
  name: string
  asset_type: string
  source: string
  source_info?: {
    model_id?: number
    version_id?: number
    model_name?: string
    version_name?: string
    creator?: string
    repo_id?: string
    filename?: string
  }
  size?: number
  installed: boolean
  status: string
  base_model_hint?: string
  url?: string
  filename?: string
  local_path?: string
  version_name?: string
  sha256?: string
  provider_name?: string
  description?: string
}

interface PreviewInfo {
  filename: string
  url?: string
  nsfw: boolean
  width?: number
  height?: number
  meta?: Record<string, any>
  media_type?: MediaType
  duration?: number
  thumbnail_url?: string
  has_audio?: boolean
}

interface ParametersInfo {
  sampler?: string
  scheduler?: string
  steps?: number
  cfg_scale?: number
  clip_skip?: number
  denoise?: number
  width?: number
  height?: number
  seed?: number
  hires_fix?: boolean
  hires_upscaler?: string
  hires_steps?: number
  hires_denoise?: number
}

interface ModelInfoResponse {
  model_type?: string
  base_model?: string
  trigger_words: string[]
  usage_tips?: string
  hash_autov2?: string
  civitai_air?: string
  download_count?: number
  rating?: number
  published_at?: string
  strength_recommended?: number
}

interface PackDetail {
  name: string
  version: string
  description?: string
  author?: string
  tags: string[]
  user_tags: string[]
  source_url?: string
  created_at?: string
  installed: boolean
  has_unresolved: boolean
  all_installed: boolean
  can_generate: boolean
  assets: AssetInfo[]
  previews: PreviewInfo[]
  workflows: Array<{
    name: string
    filename: string
    description?: string
    is_default: boolean
    local_path?: string
    has_symlink: boolean
    symlink_valid: boolean
    symlink_path?: string
  }>
  custom_nodes: Array<{
    name: string
    git_url?: string
    installed: boolean
  }>
  docs: Record<string, string>
  parameters?: ParametersInfo
  model_info?: ModelInfoResponse
}

interface LocalModel {
  name: string
  path: string
  type: string
  size?: number
}

// Base model search result - unified format for all sources
interface BaseModelResult {
  model_id: string
  model_name: string
  creator?: string
  download_count: number
  version_id?: string
  version_name?: string
  file_name: string
  size_kb: number
  size_gb?: number
  download_url: string
  base_model?: string
  source: string  // 'civitai', 'huggingface', etc.
  source_url?: string
}

interface BaseModelSearchResponse {
  results: BaseModelResult[]
  total_found: number
  source: string
  search_query: string
  search_method?: string
}

export function PackDetailPage() {
  const { packName: packNameParam } = useParams<{ packName: string }>()  // Route uses :packName
  const navigate = useNavigate()
  const queryClient = useQueryClient()


  const [fullscreenIndex, setFullscreenIndex] = useState<number>(-1)
  const isFullscreenOpen = fullscreenIndex >= 0



  // Zoom state - extended with xs and xl for more granular control
  const [cardSize, setCardSize] = useState<'xs' | 'sm' | 'md' | 'lg' | 'xl'>('sm')

  const zoomIn = () => {
    if (cardSize === 'xs') setCardSize('sm')
    else if (cardSize === 'sm') setCardSize('md')
    else if (cardSize === 'md') setCardSize('lg')
    else if (cardSize === 'lg') setCardSize('xl')
  }

  const zoomOut = () => {
    if (cardSize === 'xl') setCardSize('lg')
    else if (cardSize === 'lg') setCardSize('md')
    else if (cardSize === 'md') setCardSize('sm')
    else if (cardSize === 'sm') setCardSize('xs')
  }

  const gridClass = {
    xs: 'grid-cols-10 gap-1',
    sm: 'grid-cols-8 gap-2',
    md: 'grid-cols-6 gap-3',
    lg: 'grid-cols-4 gap-4',
    xl: 'grid-cols-3 gap-5'
  }[cardSize]
  const [showBaseModelResolver, setShowBaseModelResolver] = useState(false)
  const [baseModelSearch, setBaseModelSearch] = useState('')
  const [selectedBaseModel, setSelectedBaseModel] = useState<BaseModelResult | LocalModel | null>(null)
  const [resolverTab, setResolverTab] = useState<'local' | 'civitai' | 'huggingface'>('local')
  const [searchTrigger, setSearchTrigger] = useState('')
  const [showEditModal, setShowEditModal] = useState(false)
  const [editUserTags, setEditUserTags] = useState<string[]>([])
  const [newTag, setNewTag] = useState('')
  const [downloadingAssets, setDownloadingAssets] = useState<Set<string>>(new Set())
  const [showParametersModal, setShowParametersModal] = useState(false)
  const [editParameters, setEditParameters] = useState<Record<string, string>>({})
  const [newParamKey, setNewParamKey] = useState('')
  const [newParamValue, setNewParamValue] = useState('')
  const [showUploadWorkflowModal, setShowUploadWorkflowModal] = useState(false)
  const [uploadWorkflowFile, setUploadWorkflowFile] = useState<File | null>(null)
  const [uploadWorkflowName, setUploadWorkflowName] = useState('')
  const [uploadWorkflowDescription, setUploadWorkflowDescription] = useState('')

  // Local model import state
  const [showImportModelModal, setShowImportModelModal] = useState(false)
  const [importModelFile, setImportModelFile] = useState<File | null>(null)
  const [importModelName, setImportModelName] = useState('')
  const [importModelBaseModel, setImportModelBaseModel] = useState('')
  const [importModelType, setImportModelType] = useState<'checkpoint' | 'lora' | 'vae'>('checkpoint')
  const [isImportingModel, setIsImportingModel] = useState(false)

  // HuggingFace file selection
  const [expandedHfRepo, setExpandedHfRepo] = useState<string | null>(null)
  const [hfFiles, setHfFiles] = useState<Array<{
    filename: string
    size_bytes: number
    size_gb?: number
    download_url: string
    is_recommended: boolean
    file_type: string
  }>>([])
  const [hfFilesLoading, setHfFilesLoading] = useState(false)

  // Decode pack name from URL
  const packName = packNameParam ? decodeURIComponent(packNameParam) : ''

  console.log('[PackDetailPage] packNameParam from URL:', packNameParam)
  console.log('[PackDetailPage] Decoded packName:', packName)

  // Fetch pack details
  const { data: pack, isLoading, error } = useQuery<PackDetail>({
    queryKey: ['pack', packName],
    queryFn: async () => {
      console.log('[PackDetailPage] Fetching pack:', packName)
      const res = await fetch(`/api/packs/${encodeURIComponent(packName)}`)
      console.log('[PackDetailPage] Response status:', res.status)

      if (!res.ok) {
        const errText = await res.text()
        console.error('[PackDetailPage] Error response:', errText)
        throw new Error(`Failed to fetch pack: ${res.status} - ${errText}`)
      }

      const data = await res.json()
      console.log('[PackDetailPage] Received pack data:', JSON.stringify(data, null, 2))
      return data
    },
    enabled: !!packName,
  })

  // Create MediaItems for viewer
  const mediaItems = pack?.previews.map(p => ({
    url: p.url || '',
    type: p.media_type === 'video' ? 'video' as const : 'image' as const,
    thumbnailUrl: p.thumbnail_url,
    nsfw: p.nsfw,
    width: p.width,
    height: p.height,
    meta: p.meta
  })) || []

  const openFullscreen = (index: number) => setFullscreenIndex(index)
  const closeFullscreen = () => setFullscreenIndex(-1)

  // Fetch local models from ComfyUI for resolver
  const { data: localModels = [] } = useQuery<LocalModel[]>({
    queryKey: ['local-models', 'checkpoints'],
    queryFn: async () => {
      console.log('[PackDetailPage] Fetching local checkpoints from ComfyUI...')
      const res = await fetch('/api/comfyui/models/checkpoints')
      console.log('[PackDetailPage] Local models response:', res.status)
      if (!res.ok) {
        console.error('[PackDetailPage] Failed to fetch local models')
        return []
      }
      const data = await res.json()
      console.log('[PackDetailPage] Local models:', data)
      // Map ComfyUI models to LocalModel format
      return (data || []).map((m: any) => ({
        name: m.name,
        path: m.path,
        type: 'checkpoint',
        size: m.size,
      }))
    },
    enabled: showBaseModelResolver,
  })

  // Search for base models - unified for all sources (civitai, huggingface, etc.)
  const { data: searchResponse, isLoading: isSearching } = useQuery<BaseModelSearchResponse>({
    queryKey: ['base-models-search', resolverTab, searchTrigger],
    queryFn: async () => {
      if (!searchTrigger || searchTrigger.length < 2) {
        return { results: [], total_found: 0, source: resolverTab, search_query: '' }
      }

      // Only search for civitai and huggingface tabs
      if (resolverTab !== 'civitai' && resolverTab !== 'huggingface') {
        return { results: [], total_found: 0, source: resolverTab, search_query: '' }
      }

      console.log(`[PackDetailPage] Searching ${resolverTab} for:`, searchTrigger)

      const params = new URLSearchParams({
        query: searchTrigger,
        source: resolverTab,  // 'civitai' or 'huggingface'
        limit: '30',
        max_batches: '3',
      })

      const res = await fetch(`/api/browse/base-models/search?${params}`)

      if (!res.ok) {
        const errText = await res.text()
        console.error(`[PackDetailPage] ${resolverTab} search failed:`, res.status, errText)
        throw new Error(`Search failed: ${res.status}`)
      }

      const data = await res.json()
      console.log(`[PackDetailPage] ${resolverTab} search results:`, data)
      return data
    },
    enabled: showBaseModelResolver && (resolverTab === 'civitai' || resolverTab === 'huggingface') && searchTrigger.length >= 2,
    staleTime: 60000, // Cache for 1 minute
  })

  const searchResults = searchResponse?.results || []

  // Fetch active downloads for progress tracking
  const { data: activeDownloads = [], refetch: refetchActiveDownloads } = useQuery<DownloadProgress[]>({
    queryKey: ['downloads-active'],
    queryFn: async () => {
      try {
        const res = await fetch('/api/packs/downloads/active')
        if (!res.ok) return []
        return res.json()
      } catch {
        return []
      }
    },
    // Poll when there are active downloads for THIS pack OR when we just started a download
    refetchInterval: (query) => {
      const downloads = query.state.data as DownloadProgress[] | undefined
      // Check if any download is active for this pack
      const hasActiveForPack = downloads?.some(
        d => d.pack_name === packName && (d.status === 'downloading' || d.status === 'pending')
      )
      // Also check local state (for immediate feedback after starting download)
      return (hasActiveForPack || downloadingAssets.size > 0) ? 1000 : false
    },
  })

  // Get download progress for a specific asset
  const getAssetDownload = (assetName: string): DownloadProgress | undefined => {
    return activeDownloads.find(d => d.asset_name === assetName && d.pack_name === packName)
  }

  // Sync downloadingAssets with activeDownloads (for when page is revisited)
  useEffect(() => {
    const activeForPack = activeDownloads.filter(
      d => d.pack_name === packName && (d.status === 'downloading' || d.status === 'pending')
    )
    if (activeForPack.length > 0) {
      const newSet = new Set(activeForPack.map(d => d.asset_name))
      setDownloadingAssets(prev => {
        // Only update if different to avoid infinite loops
        if (prev.size !== newSet.size || [...prev].some(x => !newSet.has(x))) {
          return newSet
        }
        return prev
      })
    }
  }, [activeDownloads, packName])

  // Trigger search on button click or Enter
  const handleSearch = () => {
    if (baseModelSearch.length >= 2) {
      console.log(`[PackDetailPage] Triggering ${resolverTab} search:`, baseModelSearch)
      setSearchTrigger(baseModelSearch)
    }
  }

  // Reset search when switching tabs
  useEffect(() => {
    setSearchTrigger('')
  }, [resolverTab])

  // Watch for completed downloads and cleanup
  useEffect(() => {
    if (activeDownloads.length === 0) return

    // Find completed downloads for this pack
    const completed = activeDownloads.filter(
      d => d.pack_name === packName && (d.status === 'completed' || d.status === 'failed')
    )

    if (completed.length > 0) {
      console.log('[PackDetailPage] Completed downloads:', completed.map(d => d.asset_name))

      // Remove completed from downloadingAssets
      setDownloadingAssets(prev => {
        const next = new Set(prev)
        completed.forEach(d => next.delete(d.asset_name))
        return next
      })

      // Refresh pack data to get updated status
      queryClient.invalidateQueries({ queryKey: ['pack', packName] })
    }
  }, [activeDownloads, packName, queryClient])

  // Resolve base model mutation
  const resolveBaseModelMutation = useMutation({
    mutationFn: async (data: { pack_name: string; model_path?: string; download_url?: string; source?: string; file_name?: string; size_kb?: number }) => {
      console.log('[PackDetailPage] Resolving base model:', data)
      const res = await fetch(`/api/packs/${encodeURIComponent(data.pack_name)}/resolve-base-model`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(data),
      })
      if (!res.ok) {
        const errText = await res.text()
        throw new Error(`Failed to resolve base model: ${errText}`)
      }
      return res.json()
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['pack', packName] })
      queryClient.invalidateQueries({ queryKey: ['packs'] })
      setShowBaseModelResolver(false)
    },
  })

  // Delete mutation
  const deleteMutation = useMutation({
    mutationFn: async () => {
      console.log('[PackDetailPage] Deleting pack:', packName)
      const res = await fetch(`/api/packs/${encodeURIComponent(packName)}`, { method: 'DELETE' })
      if (!res.ok) {
        const errText = await res.text()
        throw new Error(`Failed to delete pack: ${errText}`)
      }
      return res.json()
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['packs'] })
      navigate('/')
    },
  })

  // Use pack - activate work profile
  const usePackMutation = useMutation({
    mutationFn: async () => {
      console.log('[PackDetailPage] Activating pack:', packName)
      const res = await fetch('/api/profiles/use', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          pack: packName,
          ui_set: 'local',
          sync: true,
        }),
      })
      if (!res.ok) {
        const errText = await res.text()
        throw new Error(`Failed to activate pack: ${errText}`)
      }
      return res.json()
    },
    onSuccess: (data) => {
      // Refresh profiles status for Header dropdown
      queryClient.invalidateQueries({ queryKey: ['profiles-status'] })
      // Show toast with new profile name
      const profileName = data?.new_profile || `work__${packName}`
      toast.success(`Activated: ${profileName}`)
    },
    onError: (error: Error) => {
      toast.error(`Failed to activate: ${error.message}`)
    },
  })

  // Fetch HuggingFace files for a repo
  const fetchHfFiles = async (repoId: string) => {
    setHfFilesLoading(true)
    try {
      const res = await fetch(`/api/browse/huggingface/files?repo_id=${encodeURIComponent(repoId)}`)
      if (res.ok) {
        const data = await res.json()
        setHfFiles(data.files || [])
      } else {
        setHfFiles([])
      }
    } catch (e) {
      console.error('[PackDetailPage] Failed to fetch HF files:', e)
      setHfFiles([])
    }
    setHfFilesLoading(false)
  }

  // Download single asset mutation
  const downloadAssetMutation = useMutation({
    mutationFn: async (asset: AssetInfo) => {
      console.log('[PackDetailPage] Starting download for:', asset.name)
      setDownloadingAssets(prev => new Set(prev).add(asset.name))

      const res = await fetch(`/api/packs/${encodeURIComponent(packName)}/download-asset`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          asset_name: asset.name,
          asset_type: asset.asset_type,
          url: asset.url,
          filename: asset.filename,
        }),
      })
      if (!res.ok) {
        const errText = await res.text()
        throw new Error(`Failed to start download: ${errText}`)
      }
      const data = await res.json()
      console.log('[PackDetailPage] Download started:', data)
      return data
    },
    onSuccess: (data, asset) => {
      // DON'T remove from downloadingAssets here - let activeDownloads query handle state
      // The download is still running in the background!
      console.log('[PackDetailPage] Download request accepted for:', asset.name, 'download_id:', data.download_id)
      // Refetch active downloads to show progress
      refetchActiveDownloads()
    },
    onError: (error, asset) => {
      console.error('[PackDetailPage] Download failed for:', asset.name, error)
      setDownloadingAssets(prev => {
        const next = new Set(prev)
        next.delete(asset.name)
        return next
      })
    },
  })

  // Download all pending assets mutation
  const downloadAllMutation = useMutation({
    mutationFn: async () => {
      console.log('[PackDetailPage] Downloading all pending assets')
      try {
        const res = await fetch(`/api/packs/${encodeURIComponent(packName)}/download-all`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
        })
        console.log('[PackDetailPage] Download-all response status:', res.status)
        const text = await res.text()
        console.log('[PackDetailPage] Download-all response:', text)
        if (!res.ok) {
          throw new Error(`Failed to start downloads: ${text}`)
        }
        return JSON.parse(text)
      } catch (e) {
        console.error('[PackDetailPage] Download-all error:', e)
        throw e
      }
    },
    onSuccess: (data) => {
      console.log('[PackDetailPage] Download-all success:', data)
      queryClient.invalidateQueries({ queryKey: ['pack', packName] })
    },
    onError: (err) => {
      console.error('[PackDetailPage] Download-all mutation error:', err)
    },
  })

  // Update pack (user tags) mutation
  const updatePackMutation = useMutation({
    mutationFn: async (data: { user_tags: string[] }) => {
      console.log('[PackDetailPage] Updating pack:', data)
      const res = await fetch(`/api/packs/${encodeURIComponent(packName)}`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(data),
      })
      if (!res.ok) {
        const errText = await res.text()
        throw new Error(`Failed to update pack: ${errText}`)
      }
      return res.json()
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['pack', packName] })
      queryClient.invalidateQueries({ queryKey: ['packs'] })
      setShowEditModal(false)
    },
  })



  // Update parameters mutation
  const updateParametersMutation = useMutation({
    mutationFn: async (data: { strength_recommended?: number; cfg_scale?: number; steps?: number; sampler?: string }) => {
      console.log('[PackDetailPage] Updating parameters:', data)
      const res = await fetch(`/api/packs/${encodeURIComponent(packName)}/parameters`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(data),
      })
      if (!res.ok) {
        const errText = await res.text()
        throw new Error(`Failed to update parameters: ${errText}`)
      }
      return res.json()
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['pack', packName] })
      setShowParametersModal(false)
    },
  })

  // Generate default workflow mutation
  const generateWorkflowMutation = useMutation({
    mutationFn: async () => {
      console.log('[PackDetailPage] Generating default workflow')
      const res = await fetch(`/api/packs/${encodeURIComponent(packName)}/generate-workflow`, {
        method: 'POST',
      })
      if (!res.ok) {
        const errText = await res.text()
        throw new Error(`Failed to generate workflow: ${errText}`)
      }
      return res.json()
    },
    onSuccess: (data) => {
      console.log('[PackDetailPage] Workflow generated:', data)
      queryClient.invalidateQueries({ queryKey: ['pack', packName] })
    },
  })

  // Create workflow symlink mutation
  const createSymlinkMutation = useMutation({
    mutationFn: async (filename: string) => {
      console.log('[PackDetailPage] Creating symlink for:', filename)
      const res = await fetch(`/api/packs/${encodeURIComponent(packName)}/workflow/symlink`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ filename }),
      })
      if (!res.ok) {
        const errText = await res.text()
        throw new Error(`Failed to create symlink: ${errText}`)
      }
      return res.json()
    },
    onSuccess: (data) => {
      console.log('[PackDetailPage] Symlink created:', data)
      queryClient.invalidateQueries({ queryKey: ['pack', packName] })
    },
  })

  // Remove workflow symlink mutation
  const removeSymlinkMutation = useMutation({
    mutationFn: async (filename: string) => {
      console.log('[PackDetailPage] Removing symlink for:', filename)
      const res = await fetch(`/api/packs/${encodeURIComponent(packName)}/workflow/${encodeURIComponent(filename)}/symlink`, {
        method: 'DELETE',
      })
      if (!res.ok) {
        const errText = await res.text()
        throw new Error(`Failed to remove symlink: ${errText}`)
      }
      return res.json()
    },
    onSuccess: (data) => {
      console.log('[PackDetailPage] Symlink removed:', data)
      queryClient.invalidateQueries({ queryKey: ['pack', packName] })
    },
  })

  // Delete workflow mutation
  const deleteWorkflowMutation = useMutation({
    mutationFn: async (filename: string) => {
      console.log('[PackDetailPage] Deleting workflow:', filename)
      const res = await fetch(`/api/packs/${encodeURIComponent(packName)}/workflow/${encodeURIComponent(filename)}`, {
        method: 'DELETE',
      })
      if (!res.ok) {
        const errText = await res.text()
        throw new Error(`Failed to delete workflow: ${errText}`)
      }
      return res.json()
    },
    onSuccess: (data) => {
      console.log('[PackDetailPage] Workflow deleted:', data)
      queryClient.invalidateQueries({ queryKey: ['pack', packName] })
    },
  })

  // Delete resource (blob) mutation
  const deleteResourceMutation = useMutation({
    mutationFn: async ({ depId, deleteDependency = false }: { depId: string; deleteDependency?: boolean }) => {
      console.log('[PackDetailPage] Deleting resource:', depId, deleteDependency ? '(with dependency)' : '')
      const res = await fetch(
        `/api/packs/${encodeURIComponent(packName)}/dependencies/${encodeURIComponent(depId)}/resource?delete_dependency=${deleteDependency}`,
        { method: 'DELETE' }
      )
      if (!res.ok) {
        const errText = await res.text()
        throw new Error(`Failed to delete resource: ${errText}`)
      }
      return res.json()
    },
    onSuccess: (data) => {
      console.log('[PackDetailPage] Resource deleted:', data)
      queryClient.invalidateQueries({ queryKey: ['pack', packName] })
    },
  })

  // Upload workflow file mutation
  const uploadWorkflowMutation = useMutation({
    mutationFn: async (data: { file: File; name: string; description?: string }) => {
      console.log('[PackDetailPage] Uploading workflow:', data.name)
      const formData = new FormData()
      formData.append('file', data.file)
      formData.append('name', data.name)
      if (data.description) formData.append('description', data.description)

      const res = await fetch(`/api/packs/${encodeURIComponent(packName)}/workflow/upload-file`, {
        method: 'POST',
        body: formData,
      })
      if (!res.ok) {
        const errText = await res.text()
        throw new Error(`Failed to upload workflow: ${errText}`)
      }
      return res.json()
    },
    onSuccess: (data) => {
      console.log('[PackDetailPage] Workflow uploaded:', data)
      queryClient.invalidateQueries({ queryKey: ['pack', packName] })
      setShowUploadWorkflowModal(false)
    },
  })

  // Extract base model hint from description
  const extractBaseModelHint = (description?: string): string | null => {
    if (!description) return null

    const patterns = [
      /trained on\s+([A-Za-z0-9\s\-_.]+)/i,
      /base model[:\s]+([A-Za-z0-9\s\-_.]+)/i,
      /requires?\s+([A-Za-z0-9\s\-_.]+)\s+(?:checkpoint|model)/i,
      /for\s+([A-Za-z0-9\s\-_.]+)\s+(?:checkpoint|model)/i,
      /(Illustrious|Pony|SDXL|SD\s*1\.5|SD\s*2\.1|Flux|AuraFlow)/i,
    ]

    for (const pattern of patterns) {
      const match = description.match(pattern)
      if (match) return match[1].trim()
    }

    return null
  }

  // Initialize search with hint from description
  useEffect(() => {
    if (showBaseModelResolver && pack?.description) {
      const hint = extractBaseModelHint(pack.description)
      if (hint) setBaseModelSearch(hint)
    }
  }, [showBaseModelResolver, pack?.description])

  // Also check model_info for base_model hint
  useEffect(() => {
    if (showBaseModelResolver && pack?.model_info?.base_model) {
      setBaseModelSearch(pack.model_info.base_model)
    }
  }, [showBaseModelResolver, pack?.model_info?.base_model])

  // Filter local models
  const filteredLocalModels = localModels.filter(m =>
    !baseModelSearch || m.name.toLowerCase().includes(baseModelSearch.toLowerCase())
  )

  // Format size
  const formatSize = (bytes?: number) => {
    if (!bytes) return ''
    const gb = bytes / (1024 * 1024 * 1024)
    if (gb >= 1) return `${gb.toFixed(1)} GB`
    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
  }

  const copyToClipboard = (text: string) => {
    navigator.clipboard.writeText(text)
  }

  // Debug log
  console.log('[PackDetailPage] Render state:', { isLoading, error: error?.message, hasData: !!pack })

  if (isLoading) {
    return (
      <BreathingOrb
        size="lg"
        text="Loading pack..."
        subtext={packName}
        className="py-20"
      />
    )
  }

  if (error) {
    return (
      <div className="space-y-4">
        <button
          onClick={() => navigate('/')}
          className="flex items-center gap-2 text-text-muted hover:text-text-primary transition-colors"
        >
          <ArrowLeft className="w-5 h-5" />
          Back to Packs
        </button>
        <div className="bg-red-900/20 border border-red-500/50 rounded-xl p-6">
          <h2 className="text-xl font-bold text-red-400 mb-2">Failed to load pack</h2>
          <p className="text-red-300 mb-4">{(error as Error).message}</p>
          <pre className="text-xs text-red-200 bg-black/30 p-3 rounded overflow-auto">
            Pack name: {packName}
            {'\n'}URL: /api/packs/{encodeURIComponent(packName)}
          </pre>
        </div>
      </div>
    )
  }

  if (!pack) {
    return (
      <div className="space-y-4">
        <button
          onClick={() => navigate('/')}
          className="flex items-center gap-2 text-text-muted hover:text-text-primary transition-colors"
        >
          <ArrowLeft className="w-5 h-5" />
          Back to Packs
        </button>
        <div className="text-center py-20">
          <p className="text-text-muted">Pack not found: {packName}</p>
          <Button onClick={() => navigate('/')} className="mt-4">Go Back</Button>
        </div>
      </div>
    )
  }

  // Check if all dependencies are installed (not just resolved)
  const allDependenciesInstalled = pack.all_installed === true
  const needsBaseModel = pack.has_unresolved || !allDependenciesInstalled
  const baseModelHint = pack.model_info?.base_model || extractBaseModelHint(pack.description)

  return (
    <div className="space-y-6">
      {/* Fullscreen image viewer */}
      {/* Fullscreen image viewer */}
      {/* Fullscreen media viewer */}
      <FullscreenMediaViewer
        items={mediaItems}
        initialIndex={fullscreenIndex}
        isOpen={isFullscreenOpen}
        onClose={closeFullscreen}
        onIndexChange={setFullscreenIndex}
      />

      {/* Base Model Resolver Modal */}
      {showBaseModelResolver && (
        <div
          className="fixed inset-0 bg-black/80 backdrop-blur-sm flex items-center justify-center z-50 p-4"
          onClick={() => setShowBaseModelResolver(false)}
        >
          <div
            className="bg-slate-deep border border-slate-mid rounded-2xl max-w-3xl w-full max-h-[85vh] overflow-hidden flex flex-col"
            onClick={e => e.stopPropagation()}
          >
            {/* Header */}
            <div className="bg-gradient-to-r from-amber-500/20 to-orange-500/20 border-b border-amber-500/30 p-4">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-3">
                  <div className="p-2 bg-amber-500/20 rounded-xl">
                    <AlertTriangle className="w-6 h-6 text-amber-500" />
                  </div>
                  <div>
                    <h2 className="text-lg font-bold text-text-primary">Resolve Base Model</h2>
                    <p className="text-sm text-text-muted">Select or download the base checkpoint for this pack</p>
                  </div>
                </div>
                <button
                  onClick={() => setShowBaseModelResolver(false)}
                  className="p-2 hover:bg-slate-mid rounded-xl text-text-muted hover:text-text-primary transition-colors"
                >
                  <X className="w-5 h-5" />
                </button>
              </div>

              {/* Hint from description */}
              {baseModelHint && (
                <div className="mt-3 p-3 bg-slate-dark/50 rounded-xl">
                  <p className="text-sm text-text-muted">
                    <span className="text-amber-400 font-medium">Detected base model:</span>{' '}
                    <span className="text-text-primary font-mono">{baseModelHint}</span>
                  </p>
                </div>
              )}
            </div>

            {/* Tabs */}
            <div className="flex border-b border-slate-mid">
              <button
                onClick={() => setResolverTab('local')}
                className={clsx(
                  'flex-1 px-4 py-3 text-sm font-medium flex items-center justify-center gap-2 transition-colors',
                  resolverTab === 'local'
                    ? 'text-synapse border-b-2 border-synapse bg-synapse/5'
                    : 'text-text-muted hover:text-text-primary'
                )}
              >
                <HardDrive className="w-4 h-4" />
                Local Models
              </button>
              <button
                onClick={() => setResolverTab('civitai')}
                className={clsx(
                  'flex-1 px-4 py-3 text-sm font-medium flex items-center justify-center gap-2 transition-colors',
                  resolverTab === 'civitai'
                    ? 'text-synapse border-b-2 border-synapse bg-synapse/5'
                    : 'text-text-muted hover:text-text-primary'
                )}
              >
                <Globe className="w-4 h-4" />
                Civitai
              </button>
              <button
                onClick={() => setResolverTab('huggingface')}
                className={clsx(
                  'flex-1 px-4 py-3 text-sm font-medium flex items-center justify-center gap-2 transition-colors',
                  resolverTab === 'huggingface'
                    ? 'text-synapse border-b-2 border-synapse bg-synapse/5'
                    : 'text-text-muted hover:text-text-primary'
                )}
              >
                <Database className="w-4 h-4" />
                Hugging Face
              </button>
            </div>

            {/* Search */}
            <div className="p-4 border-b border-slate-mid">
              <div className="flex gap-2">
                <div className="relative flex-1">
                  <Search className="absolute left-4 top-1/2 -translate-y-1/2 w-5 h-5 text-text-muted" />
                  <input
                    type="text"
                    value={baseModelSearch}
                    onChange={(e) => setBaseModelSearch(e.target.value)}
                    onKeyDown={(e) => {
                      if (e.key === 'Enter' && (resolverTab === 'civitai' || resolverTab === 'huggingface')) {
                        handleSearch()
                      }
                    }}
                    placeholder={
                      resolverTab === 'local'
                        ? 'Filter local models...'
                        : resolverTab === 'civitai'
                          ? 'Search checkpoints (e.g. Illustrious, Pony, SDXL)...'
                          : 'Search models (e.g. stable-diffusion, sdxl, flux)...'
                    }
                    className="w-full pl-12 pr-4 py-3 bg-slate-dark border border-slate-mid rounded-xl text-text-primary placeholder-text-muted focus:outline-none focus:border-synapse transition-colors"
                  />
                </div>
                {(resolverTab === 'civitai' || resolverTab === 'huggingface') && (
                  <Button
                    onClick={handleSearch}
                    disabled={baseModelSearch.length < 2 || isSearching}
                    className="px-6"
                  >
                    {isSearching ? (
                      <Loader2 className="w-5 h-5 animate-spin" />
                    ) : (
                      <Search className="w-5 h-5" />
                    )}
                  </Button>
                )}
              </div>
              {(resolverTab === 'civitai' || resolverTab === 'huggingface') && searchResponse?.search_method && (
                <p className="text-xs text-text-muted mt-2">
                  Search method: <span className="text-synapse">{searchResponse.search_method}</span>
                  {searchResponse.total_found > 0 && ` • Found ${searchResponse.total_found} models`}
                </p>
              )}
            </div>

            {/* Content */}
            <div className="flex-1 overflow-y-auto p-4">
              {resolverTab === 'local' && (
                <div className="space-y-4">
                  {/* Import new model button */}
                  <div className="flex items-center justify-between p-3 bg-slate-dark/50 rounded-xl border border-slate-mid/50">
                    <div className="flex items-center gap-3">
                      <div className="p-2 bg-green-500/20 rounded-lg">
                        <FolderOpen className="w-5 h-5 text-green-400" />
                      </div>
                      <div>
                        <p className="text-sm font-medium text-text-primary">Import Local Model</p>
                        <p className="text-xs text-text-muted">Import a model from your computer to Synapse</p>
                      </div>
                    </div>
                    <Button
                      size="sm"
                      variant="primary"
                      onClick={() => setShowImportModelModal(true)}
                    >
                      <FolderOpen className="w-4 h-4" />
                      Browse...
                    </Button>
                  </div>

                  {/* Existing local models */}
                  <div className="space-y-2">
                    {filteredLocalModels.length === 0 ? (
                      <p className="text-center text-text-muted py-4">
                        No local checkpoints found. Use the button above to import one, or search Civitai/HuggingFace.
                      </p>
                    ) : (
                      <>
                        <p className="text-xs text-text-muted mb-2">
                          Found {filteredLocalModels.length} local checkpoint{filteredLocalModels.length !== 1 ? 's' : ''}:
                        </p>
                        {filteredLocalModels.map(model => (
                          <button
                            key={model.path}
                            onClick={() => setSelectedBaseModel(model)}
                            className={clsx(
                              'w-full p-4 rounded-xl border text-left transition-all',
                              selectedBaseModel && 'path' in selectedBaseModel && selectedBaseModel.path === model.path
                                ? 'bg-synapse/20 border-synapse'
                                : 'bg-slate-dark border-slate-mid hover:border-synapse/50'
                            )}
                          >
                            <div className="flex items-center justify-between">
                              <div className="flex items-center gap-3">
                                <Package className="w-5 h-5 text-synapse" />
                                <div>
                                  <p className="font-medium text-text-primary">{model.name}</p>
                                  <p className="text-xs text-text-muted truncate max-w-md">{model.path}</p>
                                </div>
                              </div>
                              {model.size && (
                                <span className="text-sm text-text-muted">{formatSize(model.size)}</span>
                              )}
                            </div>
                          </button>
                        ))}
                      </>
                    )}
                  </div>
                </div>
              )}

              {resolverTab === 'civitai' && (
                <div className="space-y-2">
                  {isSearching ? (
                    <BreathingOrb
                      size="md"
                      text="Searching Civitai..."
                      subtext="This may take a moment"
                      className="py-12"
                    />
                  ) : !searchTrigger ? (
                    <div className="text-center py-8 text-text-muted">
                      <Globe className="w-12 h-12 mx-auto mb-3 opacity-50" />
                      <p>Enter a search term and click Search</p>
                      <p className="text-sm mt-2">Try: Illustrious, Pony, SDXL, Flux, etc.</p>
                    </div>
                  ) : searchResults.length === 0 ? (
                    <p className="text-center text-text-muted py-8">
                      No checkpoints found. Try a different search term.
                    </p>
                  ) : (
                    <>
                      <p className="text-sm text-text-muted mb-3">
                        Showing {searchResults.length} of {searchResponse?.total_found || 0} results
                      </p>
                      {searchResults.map((result, resultIdx) => (
                        <button
                          key={`civitai-${result.model_id}-${result.version_id}-${result.file_name || ''}-${resultIdx}`}
                          onClick={() => setSelectedBaseModel(result)}
                          className={clsx(
                            'w-full p-4 rounded-xl border text-left transition-all',
                            selectedBaseModel && 'model_id' in selectedBaseModel &&
                              selectedBaseModel.model_id === result.model_id &&
                              selectedBaseModel.file_name === result.file_name
                              ? 'bg-synapse/20 border-synapse'
                              : 'bg-slate-dark border-slate-mid hover:border-synapse/50'
                          )}
                        >
                          <div className="flex items-center justify-between gap-4">
                            <div className="flex items-center gap-3 min-w-0 flex-1">
                              <Globe className="w-5 h-5 text-blue-400 flex-shrink-0" />
                              <div className="min-w-0">
                                <p className="font-medium text-text-primary truncate">{result.model_name}</p>
                                <div className="flex items-center gap-2 text-xs text-text-muted mt-0.5">
                                  <span className="text-synapse">{result.version_name}</span>
                                  {result.creator && <span>by {result.creator}</span>}
                                  {result.base_model && (
                                    <span className="px-1.5 py-0.5 bg-slate-mid rounded">{result.base_model}</span>
                                  )}
                                </div>
                              </div>
                            </div>
                            <div className="flex flex-col items-end gap-1 flex-shrink-0">
                              <span className="text-sm font-medium text-text-primary">
                                {result.size_gb ? `${result.size_gb} GB` : ''}
                              </span>
                              <span className="text-xs text-text-muted">
                                {result.download_count.toLocaleString()} downloads
                              </span>
                            </div>
                          </div>
                          <p className="text-xs text-text-muted mt-2 truncate">{result.file_name}</p>
                        </button>
                      ))}
                    </>
                  )}
                </div>
              )}

              {resolverTab === 'huggingface' && (
                <div className="space-y-2">
                  {isSearching ? (
                    <BreathingOrb
                      size="md"
                      text="Searching Hugging Face..."
                      subtext="Looking for diffusion models"
                      className="py-12"
                    />
                  ) : !searchTrigger ? (
                    <div className="text-center py-8 text-text-muted">
                      <Database className="w-12 h-12 mx-auto mb-3 opacity-50" />
                      <p>Enter a search term and click Search</p>
                      <p className="text-sm mt-2">Try: stable-diffusion, sdxl, flux, etc.</p>
                    </div>
                  ) : searchResults.length === 0 ? (
                    <p className="text-center text-text-muted py-8">
                      No models found. Try a different search term.
                    </p>
                  ) : (
                    <>
                      <p className="text-sm text-text-muted mb-3">
                        Showing {searchResults.length} of {searchResponse?.total_found || 0} results
                      </p>
                      {searchResults.map((result) => {
                        const isExpanded = expandedHfRepo === result.model_id
                        const isSelected = selectedBaseModel && 'model_id' in selectedBaseModel && selectedBaseModel.model_id === result.model_id
                        // Get the actual selected file name (either from selectedBaseModel or original result)
                        const selectedFileName = isSelected && selectedBaseModel && 'file_name' in selectedBaseModel
                          ? selectedBaseModel.file_name
                          : result.file_name
                        const isCustomFile = isSelected && selectedFileName !== result.file_name

                        return (
                          <div key={result.model_id} className="space-y-2">
                            <div
                              className={clsx(
                                'w-full p-4 rounded-xl border text-left transition-all',
                                isSelected
                                  ? 'bg-synapse/20 border-synapse'
                                  : 'bg-slate-dark border-slate-mid hover:border-synapse/50'
                              )}
                            >
                              <div className="flex items-center justify-between gap-4">
                                <button
                                  onClick={() => {
                                    // Only set if not already selected (preserve manual file selection)
                                    if (!isSelected) {
                                      setSelectedBaseModel(result)
                                    }
                                  }}
                                  className="flex items-center gap-3 min-w-0 flex-1 text-left"
                                >
                                  <Database className="w-5 h-5 text-yellow-400 flex-shrink-0" />
                                  <div className="min-w-0">
                                    <p className="font-medium text-text-primary truncate">{result.model_name}</p>
                                    <div className="flex items-center gap-2 text-xs text-text-muted mt-0.5">
                                      {result.creator && <span>by {result.creator}</span>}
                                      {result.version_name && (
                                        <span className="px-1.5 py-0.5 bg-slate-mid rounded">{result.version_name}</span>
                                      )}
                                    </div>
                                  </div>
                                </button>
                                <div className="flex items-center gap-3 flex-shrink-0">
                                  <div className="flex flex-col items-end gap-1">
                                    <span className="text-sm font-medium text-text-primary">
                                      {isSelected && selectedBaseModel && 'size_gb' in selectedBaseModel && selectedBaseModel.size_gb
                                        ? `${selectedBaseModel.size_gb} GB`
                                        : result.size_gb ? `${result.size_gb} GB` : ''}
                                    </span>
                                    <span className="text-xs text-text-muted">
                                      {result.download_count.toLocaleString()} downloads
                                    </span>
                                  </div>
                                  {/* Show files button */}
                                  <button
                                    onClick={(e) => {
                                      e.stopPropagation()
                                      if (isExpanded) {
                                        setExpandedHfRepo(null)
                                        setHfFiles([])
                                      } else {
                                        setExpandedHfRepo(result.model_id)
                                        fetchHfFiles(result.model_id)
                                      }
                                    }}
                                    className="p-2 bg-slate-mid/50 rounded-lg hover:bg-slate-mid transition-colors"
                                    title={isExpanded ? "Hide files" : "Show all files"}
                                  >
                                    {isExpanded ? (
                                      <ChevronDown className="w-4 h-4 text-text-muted" />
                                    ) : (
                                      <ChevronRight className="w-4 h-4 text-text-muted" />
                                    )}
                                  </button>
                                </div>
                              </div>
                              <p className="text-xs text-text-muted mt-2 truncate">
                                Selected: <span className={isCustomFile ? "text-synapse font-medium" : ""}>{selectedFileName}</span>
                                {!isCustomFile && <span className="ml-2 text-synapse">(auto)</span>}
                                {isCustomFile && <span className="ml-2 text-green-400">(manual)</span>}
                              </p>
                            </div>

                            {/* Expanded file list */}
                            {isExpanded && (
                              <div className="ml-4 p-3 bg-slate-dark/50 rounded-lg border border-slate-mid/50">
                                {hfFilesLoading ? (
                                  <div className="flex items-center justify-center py-4">
                                    <Loader2 className="w-5 h-5 animate-spin text-synapse" />
                                    <span className="ml-2 text-sm text-text-muted">Loading files...</span>
                                  </div>
                                ) : hfFiles.length === 0 ? (
                                  <p className="text-sm text-text-muted text-center py-2">No files found</p>
                                ) : (
                                  <div className="space-y-1">
                                    <p className="text-xs text-text-muted mb-2">Select a different file:</p>
                                    {hfFiles.map((file) => (
                                      <button
                                        key={file.filename}
                                        onClick={() => {
                                          // Update selected model with new file
                                          setSelectedBaseModel({
                                            ...result,
                                            file_name: file.filename,
                                            download_url: file.download_url,
                                            size_kb: Math.round(file.size_bytes / 1024),
                                            size_gb: file.size_gb ?? undefined,
                                          })
                                          setExpandedHfRepo(null)
                                        }}
                                        className={clsx(
                                          "w-full p-2 rounded-lg text-left text-sm transition-colors flex items-center justify-between",
                                          file.filename === selectedFileName
                                            ? "bg-synapse/20 text-synapse"
                                            : "hover:bg-slate-mid/50 text-text-primary"
                                        )}
                                      >
                                        <span className="truncate flex-1">{file.filename}</span>
                                        <span className="flex items-center gap-2 flex-shrink-0 ml-2">
                                          {file.is_recommended && (
                                            <span className="px-1.5 py-0.5 bg-green-500/20 text-green-400 rounded text-xs">
                                              recommended
                                            </span>
                                          )}
                                          <span className="text-text-muted">
                                            {file.size_gb ? `${file.size_gb} GB` : ''}
                                          </span>
                                        </span>
                                      </button>
                                    ))}
                                  </div>
                                )}
                              </div>
                            )}
                          </div>
                        )
                      })}
                    </>
                  )}
                </div>
              )}
            </div>

            {/* Footer */}
            <div className="p-4 border-t border-slate-mid bg-slate-dark/50 flex gap-3">
              <Button
                variant="secondary"
                onClick={() => setShowBaseModelResolver(false)}
                className="flex-1"
              >
                Cancel
              </Button>
              <Button
                onClick={() => {
                  if (!selectedBaseModel) return

                  // Check if it's a remote model result (Civitai or HuggingFace)
                  if ('model_id' in selectedBaseModel) {
                    const model = selectedBaseModel as BaseModelResult
                    console.log(`[PackDetailPage] Saving ${model.source} base model:`, model)
                    resolveBaseModelMutation.mutate({
                      pack_name: pack.name,
                      download_url: model.download_url,
                      source: model.source,
                      file_name: model.file_name,
                      size_kb: model.size_kb,
                    })
                  } else if ('path' in selectedBaseModel) {
                    // Local model
                    const localModel = selectedBaseModel as LocalModel
                    console.log('[PackDetailPage] Using local base model:', localModel)
                    resolveBaseModelMutation.mutate({
                      pack_name: pack.name,
                      model_path: localModel.path,
                    })
                  }
                }}
                disabled={!selectedBaseModel || resolveBaseModelMutation.isPending}
                className="flex-1"
              >
                {resolveBaseModelMutation.isPending ? (
                  <Loader2 className="w-5 h-5 animate-spin" />
                ) : (
                  <>
                    <Check className="w-5 h-5" />
                    Save Selection
                  </>
                )}
              </Button>
            </div>
          </div>
        </div>
      )}

      {/* Import Model Modal */}
      {showImportModelModal && (
        <div
          className="fixed inset-0 bg-black/80 backdrop-blur-sm flex items-center justify-center z-50 p-4"
          onClick={() => setShowImportModelModal(false)}
        >
          <div
            className="bg-slate-deep border border-slate-mid rounded-2xl max-w-xl w-full overflow-hidden"
            onClick={e => e.stopPropagation()}
          >
            {/* Header */}
            <div className="bg-gradient-to-r from-green-500/20 to-emerald-500/20 border-b border-green-500/30 p-4">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-3">
                  <div className="p-2 bg-green-500/20 rounded-xl">
                    <FolderOpen className="w-6 h-6 text-green-500" />
                  </div>
                  <div>
                    <h2 className="text-lg font-bold text-text-primary">Import Local Model</h2>
                    <p className="text-sm text-text-muted">Import a model file from your computer</p>
                  </div>
                </div>
                <button
                  onClick={() => setShowImportModelModal(false)}
                  className="p-2 hover:bg-slate-mid rounded-xl text-text-muted hover:text-text-primary transition-colors"
                >
                  <X className="w-5 h-5" />
                </button>
              </div>
            </div>

            {/* Content */}
            <div className="p-6 space-y-4">
              {/* File input */}
              <div>
                <label className="block text-sm font-medium text-text-secondary mb-2">
                  Model File <span className="text-red-400">*</span>
                </label>
                <div className="relative">
                  <input
                    type="file"
                    accept=".safetensors,.ckpt,.pt,.bin"
                    onChange={(e) => {
                      const file = e.target.files?.[0]
                      if (file) {
                        setImportModelFile(file)
                        // Auto-fill name from filename
                        if (!importModelName) {
                          setImportModelName(file.name.replace(/\.(safetensors|ckpt|pt|bin)$/i, ''))
                        }
                      }
                    }}
                    className="hidden"
                    id="model-file-input"
                  />
                  <label
                    htmlFor="model-file-input"
                    className={clsx(
                      "flex items-center gap-3 p-4 border-2 border-dashed rounded-xl cursor-pointer transition-colors",
                      importModelFile
                        ? "border-green-500/50 bg-green-500/10"
                        : "border-slate-mid hover:border-synapse/50"
                    )}
                  >
                    {importModelFile ? (
                      <>
                        <Check className="w-5 h-5 text-green-400" />
                        <div className="flex-1 min-w-0">
                          <p className="text-sm font-medium text-text-primary truncate">{importModelFile.name}</p>
                          <p className="text-xs text-text-muted">{formatSize(importModelFile.size)}</p>
                        </div>
                        <button
                          onClick={(e) => {
                            e.preventDefault()
                            setImportModelFile(null)
                          }}
                          className="p-1 hover:bg-slate-mid rounded"
                        >
                          <X className="w-4 h-4 text-text-muted" />
                        </button>
                      </>
                    ) : (
                      <>
                        <FolderOpen className="w-5 h-5 text-text-muted" />
                        <div>
                          <p className="text-sm text-text-primary">Click to browse files</p>
                          <p className="text-xs text-text-muted">.safetensors, .ckpt, .pt, .bin</p>
                        </div>
                      </>
                    )}
                  </label>
                </div>
              </div>

              {/* Model type */}
              <div>
                <label className="block text-sm font-medium text-text-secondary mb-2">
                  Model Type <span className="text-red-400">*</span>
                </label>
                <select
                  value={importModelType}
                  onChange={(e) => setImportModelType(e.target.value as 'checkpoint' | 'lora' | 'vae')}
                  className="w-full px-4 py-3 bg-slate-dark border border-slate-mid rounded-xl text-text-primary focus:outline-none focus:border-synapse"
                >
                  <option value="checkpoint">Checkpoint (Base Model)</option>
                  <option value="lora">LoRA</option>
                  <option value="vae">VAE</option>
                </select>
              </div>

              {/* Display name */}
              <div>
                <label className="block text-sm font-medium text-text-secondary mb-2">
                  Display Name
                </label>
                <input
                  type="text"
                  value={importModelName}
                  onChange={(e) => setImportModelName(e.target.value)}
                  placeholder="e.g., My Custom Model"
                  className="w-full px-4 py-3 bg-slate-dark border border-slate-mid rounded-xl text-text-primary placeholder-text-muted focus:outline-none focus:border-synapse"
                />
              </div>

              {/* Base model (for checkpoints) */}
              {importModelType === 'checkpoint' && (
                <div>
                  <label className="block text-sm font-medium text-text-secondary mb-2">
                    Base Model Architecture
                  </label>
                  <select
                    value={importModelBaseModel}
                    onChange={(e) => setImportModelBaseModel(e.target.value)}
                    className="w-full px-4 py-3 bg-slate-dark border border-slate-mid rounded-xl text-text-primary focus:outline-none focus:border-synapse"
                  >
                    <option value="">Select architecture...</option>
                    <option value="SD 1.5">SD 1.5</option>
                    <option value="SD 2.1">SD 2.1</option>
                    <option value="SDXL">SDXL</option>
                    <option value="Illustrious">Illustrious</option>
                    <option value="Pony">Pony</option>
                    <option value="Flux">Flux</option>
                    <option value="AuraFlow">AuraFlow</option>
                    <option value="Other">Other</option>
                  </select>
                </div>
              )}

              {/* Info */}
              <div className="p-3 bg-blue-500/10 border border-blue-500/30 rounded-xl">
                <p className="text-xs text-blue-400">
                  <strong>Note:</strong> The file will be copied to your models directory and linked to this pack.
                  After import, it will be available as a local model option.
                </p>
              </div>
            </div>

            {/* Footer */}
            <div className="p-4 border-t border-slate-mid bg-slate-dark/50 flex gap-3">
              <Button
                variant="secondary"
                onClick={() => {
                  setShowImportModelModal(false)
                  setImportModelFile(null)
                  setImportModelName('')
                  setImportModelBaseModel('')
                }}
                className="flex-1"
              >
                Cancel
              </Button>
              <Button
                onClick={async () => {
                  if (!importModelFile) return

                  setIsImportingModel(true)
                  try {
                    const formData = new FormData()
                    formData.append('file', importModelFile)
                    formData.append('model_type', importModelType)
                    formData.append('model_name', importModelName || importModelFile.name)
                    formData.append('base_model', importModelBaseModel)

                    const res = await fetch('/api/packs/import-model', {
                      method: 'POST',
                      body: formData,
                    })

                    if (!res.ok) {
                      const error = await res.text()
                      throw new Error(error)
                    }

                    const result = await res.json()
                    console.log('[PackDetailPage] Import result:', result)

                    // Auto-select the imported model
                    setSelectedBaseModel({
                      name: result.model_name,
                      path: result.model_path,
                      type: result.model_type,
                      size: result.file_size,
                    })

                    // Close modal and refresh
                    setShowImportModelModal(false)
                    setImportModelFile(null)
                    setImportModelName('')
                    setImportModelBaseModel('')

                    // Invalidate local models query
                    queryClient.invalidateQueries({ queryKey: ['local-models'] })

                  } catch (error) {
                    console.error('[PackDetailPage] Import failed:', error)
                    alert(`Import failed: ${error}`)
                  } finally {
                    setIsImportingModel(false)
                  }
                }}
                disabled={!importModelFile || isImportingModel}
                className="flex-1"
              >
                {isImportingModel ? (
                  <>
                    <Loader2 className="w-5 h-5 animate-spin" />
                    Importing...
                  </>
                ) : (
                  <>
                    <FolderOpen className="w-5 h-5" />
                    Import Model
                  </>
                )}
              </Button>
            </div>
          </div>
        </div>
      )}

      {/* Back button */}
      <button
        onClick={() => navigate('/')}
        className="flex items-center gap-2 text-text-muted hover:text-text-primary transition-colors"
      >
        <ArrowLeft className="w-5 h-5" />
        Back to Packs
      </button>

      {/* Header */}
      <div className="flex items-start justify-between gap-6">
        <div className="flex-1">
          <h1 className="text-2xl font-bold text-text-primary">
            {pack.name}
          </h1>
          <div className="flex items-center gap-3 mt-2 flex-wrap">
            {pack.model_info?.model_type && (
              <span className="px-3 py-1 bg-synapse/20 text-synapse rounded-lg text-sm font-medium">
                {pack.model_info.model_type}
              </span>
            )}
            {pack.model_info?.base_model && (
              <span className="px-3 py-1 bg-slate-mid rounded-lg text-sm text-text-secondary">
                {pack.model_info.base_model}
              </span>
            )}
            <span className="text-text-muted text-sm">v{pack.version}</span>
          </div>
        </div>

        <div className="flex gap-2">
          {/* Use Pack - Activate work profile */}
          <Button
            variant="primary"
            onClick={() => usePackMutation.mutate()}
            disabled={usePackMutation.isPending}
          >
            {usePackMutation.isPending ? (
              <Loader2 className="w-4 h-4 animate-spin" />
            ) : (
              <Zap className="w-4 h-4" />
            )}
            Use
          </Button>

          {pack.source_url && (
            <Button
              variant="secondary"
              onClick={() => window.open(pack.source_url, '_blank')}
            >
              <ExternalLink className="w-4 h-4" />
              Source
            </Button>
          )}
          <Button
            variant="secondary"
            onClick={() => deleteMutation.mutate()}
            className="text-red-400 hover:bg-red-500/20"
          >
            <Trash2 className="w-4 h-4" />
          </Button>
        </div>
      </div>

      {/* Base Model Warning - CRITICAL */}
      {needsBaseModel && (
        <div
          className="bg-gradient-to-r from-amber-500/20 to-orange-500/20 border border-amber-500/50 rounded-xl p-4 cursor-pointer hover:border-amber-400 transition-colors"
          onClick={() => setShowBaseModelResolver(true)}
        >
          <div className="flex items-center gap-4">
            <div className="p-3 bg-amber-500/20 rounded-xl">
              <AlertTriangle className="w-8 h-8 text-amber-500" />
            </div>
            <div className="flex-1">
              <h3 className="font-semibold text-amber-400">Base Model Required</h3>
              <p className="text-text-secondary text-sm mt-1">
                This pack requires a base checkpoint model to work. Click here to select or download one.
              </p>
              {baseModelHint && (
                <p className="text-amber-400/80 text-sm mt-2">
                  Hint: <span className="font-mono">{baseModelHint}</span>
                </p>
              )}
            </div>
            <ChevronRight className="w-6 h-6 text-amber-400" />
          </div>
        </div>
      )}

      {/* Previews - 3:4 aspect ratio, clickable for fullscreen */}
      {pack.previews?.length > 0 && (
        <div>
          <div className="flex items-center justify-between mb-3">
            <h3 className="text-sm font-semibold text-text-primary">
              Previews ({pack.previews.length})
            </h3>
            {/* Zoom controls */}
            <div className="flex items-center gap-1 bg-slate-dark/80 backdrop-blur rounded-xl p-1 border border-slate-mid/50">
              <button
                onClick={zoomOut}
                disabled={cardSize === 'xs'}
                className="p-2 rounded-lg hover:bg-slate-mid disabled:opacity-30 disabled:cursor-not-allowed transition-colors"
                title="Zoom out"
              >
                <ZoomOut className="w-4 h-4 text-text-secondary" />
              </button>
              <div className="w-px h-4 bg-slate-mid" />
              <button
                onClick={zoomIn}
                disabled={cardSize === 'xl'}
                className="p-2 rounded-lg hover:bg-slate-mid disabled:opacity-30 disabled:cursor-not-allowed transition-colors"
                title="Zoom in"
              >
                <ZoomIn className="w-4 h-4 text-text-secondary" />
              </button>
            </div>
          </div>
          <div className={`grid ${gridClass}`}>
            {pack.previews.map((preview, idx) => (
              <div
                key={idx}
                className={clsx(
                  'group/card relative rounded-xl overflow-hidden cursor-pointer',
                  'bg-slate-dark',
                  // Smooth transitions for all hover effects
                  'transition-all duration-300 ease-out',
                  // Hover effects - Civitai style
                  'hover:ring-2 hover:ring-synapse/60',
                  'hover:shadow-lg hover:shadow-synapse/20',
                  'hover:scale-[1.02]',
                  'hover:-translate-y-1'
                )}
                onClick={() => openFullscreen(idx)}
              >
                <MediaPreview
                  src={preview.url || ''}
                  type={preview.media_type || 'image'}
                  thumbnailSrc={preview.thumbnail_url}
                  nsfw={preview.nsfw}
                  aspectRatio="portrait"
                  className="w-full h-full"
                  autoPlay={true}
                  playFullOnHover={true}
                />
                {/* Video indicator badge */}
                {preview.media_type === 'video' && (
                  <div className="absolute bottom-2 right-2 px-2 py-1 rounded-md bg-black/60 backdrop-blur-sm text-white text-xs font-medium flex items-center gap-1 pointer-events-none">
                    <svg className="w-3 h-3" viewBox="0 0 24 24" fill="currentColor">
                      <path d="M8 5v14l11-7z"/>
                    </svg>
                    Video
                  </div>
                )}
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Trigger Words */}
      {pack.model_info?.trigger_words && pack.model_info.trigger_words.length > 0 && (
        <Card className="p-4">
          <h3 className="text-sm font-semibold text-text-primary mb-3">Trigger Words</h3>
          <div className="flex flex-wrap gap-2">
            {pack.model_info.trigger_words.map((word, idx) => (
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
        </Card>
      )}

      {/* Model Info & Usage Tips */}
      {pack.model_info && (
        <Card className="p-4">
          <div className="flex items-center justify-between mb-3">
            <h3 className="text-sm font-semibold text-text-primary">Model Info</h3>
          </div>
          <div className="space-y-3">
            {/* Model type and base model badges */}
            <div className="flex flex-wrap gap-2">
              {pack.model_info.model_type && (
                <span className="px-3 py-1 bg-synapse/20 text-synapse rounded-lg text-sm font-medium">
                  {pack.model_info.model_type}
                </span>
              )}
              {pack.model_info.base_model && (
                <span className="px-3 py-1 bg-pulse/20 text-pulse rounded-lg text-sm">
                  Base: {pack.model_info.base_model}
                </span>
              )}
              {pack.model_info.download_count != null && pack.model_info.download_count > 0 && (
                <span className="px-3 py-1 bg-slate-mid text-text-muted rounded-lg text-sm">
                  ⬇️ {pack.model_info.download_count.toLocaleString()} downloads
                </span>
              )}
              {pack.model_info.rating != null && pack.model_info.rating > 0 && (
                <span className="px-3 py-1 bg-amber-500/20 text-amber-400 rounded-lg text-sm">
                  ⭐ {pack.model_info.rating.toFixed(1)}
                </span>
              )}
            </div>

            {pack.model_info?.usage_tips && (
              <p className="text-text-secondary text-sm">{pack.model_info.usage_tips}</p>
            )}
          </div>
        </Card>
      )}

      {/* Generation Settings - Parameters from Civitai or user-defined */}
      <Card className="p-4">
        <div className="flex items-center justify-between mb-3">
          <h3 className="text-sm font-semibold text-synapse flex items-center gap-2">
            <Info className="w-4 h-4" />
            Generation Settings
          </h3>
          <button
            onClick={() => {
              // Build initial parameters from ALL sources in pack
              const params: Record<string, string> = {}

              // From model_info
              if (pack.model_info?.strength_recommended != null) {
                params['strength'] = pack.model_info.strength_recommended.toString()
              }

              // From parameters
              if (pack.parameters) {
                if (pack.parameters.cfg_scale != null) {
                  params['cfgScale'] = pack.parameters.cfg_scale.toString()
                }
                if (pack.parameters.steps != null) {
                  params['steps'] = pack.parameters.steps.toString()
                }
                if (pack.parameters.sampler) {
                  params['sampler'] = pack.parameters.sampler
                }
                if (pack.parameters.clip_skip != null) {
                  params['clipSkip'] = pack.parameters.clip_skip.toString()
                }
                if (pack.parameters.width != null) {
                  params['width'] = pack.parameters.width.toString()
                }
                if (pack.parameters.height != null) {
                  params['height'] = pack.parameters.height.toString()
                }
                if (pack.parameters.denoise != null) {
                  params['denoise'] = pack.parameters.denoise.toString()
                }
                if (pack.parameters.scheduler) {
                  params['scheduler'] = pack.parameters.scheduler
                }
              }

              console.log('[PackDetailPage] Opening edit parameters modal with:', params)
              setEditParameters(params)
              setNewParamKey('')
              setNewParamValue('')
              setShowParametersModal(true)
            }}
            className="text-xs text-synapse hover:text-synapse/80 flex items-center gap-1"
          >
            <Edit3 className="w-3 h-3" />
            Edit
          </button>
        </div>

        {/* Parameters grid - responsive with wrapping */}
        <div className="flex flex-wrap gap-3">
          {pack.parameters?.clip_skip != null && (
            <div className="bg-slate-dark rounded-xl p-3 text-center min-w-[100px]">
              <span className="text-text-muted block text-xs mb-1">Clip Skip</span>
              <span className="text-synapse font-bold text-xl">{pack.parameters.clip_skip}</span>
            </div>
          )}
          {pack.model_info?.strength_recommended != null && (
            <div className="bg-slate-dark rounded-xl p-3 text-center min-w-[100px]">
              <span className="text-text-muted block text-xs mb-1">Strength</span>
              <span className="text-synapse font-bold text-xl">{pack.model_info.strength_recommended}</span>
            </div>
          )}
          {pack.parameters?.cfg_scale != null && (
            <div className="bg-slate-dark rounded-xl p-3 text-center min-w-[100px]">
              <span className="text-text-muted block text-xs mb-1">CFG Scale</span>
              <span className="text-text-primary font-bold text-xl">{pack.parameters.cfg_scale}</span>
            </div>
          )}
          {pack.parameters?.steps != null && (
            <div className="bg-slate-dark rounded-xl p-3 text-center min-w-[100px]">
              <span className="text-text-muted block text-xs mb-1">Steps</span>
              <span className="text-text-primary font-bold text-xl">{pack.parameters.steps}</span>
            </div>
          )}
          {pack.parameters?.sampler && (
            <div className="bg-slate-dark rounded-xl p-3 text-center min-w-[120px]">
              <span className="text-text-muted block text-xs mb-1">Sampler</span>
              <span className="text-text-primary font-medium">{pack.parameters.sampler}</span>
            </div>
          )}
          {pack.parameters?.scheduler && (
            <div className="bg-slate-dark rounded-xl p-3 text-center min-w-[120px]">
              <span className="text-text-muted block text-xs mb-1">Scheduler</span>
              <span className="text-text-primary font-medium">{pack.parameters.scheduler}</span>
            </div>
          )}
          {pack.parameters?.width != null && pack.parameters?.height != null && (
            <div className="bg-slate-dark rounded-xl p-3 text-center min-w-[120px]">
              <span className="text-text-muted block text-xs mb-1">Resolution</span>
              <span className="text-text-primary font-medium">{pack.parameters.width}×{pack.parameters.height}</span>
            </div>
          )}
          {pack.parameters?.denoise != null && (
            <div className="bg-slate-dark rounded-xl p-3 text-center min-w-[100px]">
              <span className="text-text-muted block text-xs mb-1">Denoise</span>
              <span className="text-text-primary font-bold text-xl">{pack.parameters.denoise}</span>
            </div>
          )}
        </div>

        {/* Show message if no parameters are set */}
        {!pack.parameters?.clip_skip && !pack.model_info?.strength_recommended &&
          !pack.parameters?.cfg_scale && !pack.parameters?.steps && !pack.parameters?.sampler && (
            <p className="text-text-muted text-sm text-center py-2">
              No generation parameters set. Click Edit to add some.
            </p>
          )}
      </Card>

      {/* Description */}
      {pack.description && (
        <Card className="p-4">
          <h3 className="text-sm font-semibold text-text-primary mb-3">Description</h3>
          <div
            className="prose prose-invert prose-sm max-w-none text-text-secondary"
            dangerouslySetInnerHTML={{ __html: pack.description }}
          />
        </Card>
      )}

      {/* User Tags */}
      <Card className="p-4">
        <div className="flex items-center justify-between mb-3">
          <h3 className="text-sm font-semibold text-text-primary flex items-center gap-2">
            <Tag className="w-4 h-4" />
            User Tags
          </h3>
          <button
            onClick={() => {
              setEditUserTags(pack.user_tags || [])
              setShowEditModal(true)
            }}
            className="text-xs text-synapse hover:text-synapse/80 flex items-center gap-1"
          >
            <Edit3 className="w-3 h-3" />
            Edit
          </button>
        </div>
        {pack.user_tags && pack.user_tags.length > 0 ? (
          <div className="flex flex-wrap gap-2">
            {pack.user_tags.map((tag, idx) => (
              <span
                key={idx}
                className="px-3 py-1 bg-pulse/20 text-pulse rounded-lg text-sm"
              >
                {tag}
              </span>
            ))}
          </div>
        ) : (
          <p className="text-text-muted text-sm">No user tags. Click Edit to add some.</p>
        )}
      </Card>

      {/* Assets/Dependencies */}
      <Card className="p-4">
        <div className="flex items-center justify-between mb-3">
          <h3 className="text-sm font-semibold text-text-primary">
            Dependencies ({pack.assets?.length || 0})
          </h3>
          <div className="flex items-center gap-2">
            {/* Show Download All if any asset has URL but is not installed */}
            {pack.assets?.some(a => a.url && !a.installed && !a.local_path) && (
              <Button
                size="sm"
                onClick={() => {
                  console.log('[PackDetailPage] Download All clicked')
                  downloadAllMutation.mutate()
                }}
                disabled={downloadAllMutation.isPending}
              >
                {downloadAllMutation.isPending ? (
                  <Loader2 className="w-4 h-4 animate-spin" />
                ) : (
                  <DownloadCloud className="w-4 h-4" />
                )}
                Download All
              </Button>
            )}
          </div>
        </div>

        {
          pack.assets?.length > 0 ? (
            <div className="space-y-3">
              {pack.assets.map((asset, idx) => {
                const isBaseModel = asset.asset_type === 'base_model' ||
                  asset.asset_type === 'checkpoint' ||
                  asset.name.toLowerCase().includes('base model') ||
                  asset.name.toLowerCase().includes('base_checkpoint')
                const assetDownload = getAssetDownload(asset.name)
                const isDownloading = assetDownload?.status === 'downloading' || downloadingAssets.has(asset.name)
                const isInstalled = asset.installed || asset.local_path
                // Can download if has URL and NOT installed (regardless of status)
                const canDownload = !!asset.url && !isInstalled && !isDownloading
                const needsResolve = asset.status === 'unresolved'
                // Ready to download = has URL but not installed
                const readyToDownload = !!asset.url && !isInstalled

                console.log(`[PackDetailPage] Asset ${asset.name}: status=${asset.status}, installed=${isInstalled}, url=${asset.url ? 'yes' : 'no'}, canDownload=${canDownload}, readyToDownload=${readyToDownload}, downloading=${isDownloading}`)

                return (
                  <div
                    key={idx}
                    className={clsx(
                      "p-4 rounded-xl border transition-all",
                      isDownloading
                        ? "bg-synapse/10 border-synapse/50"
                        : isInstalled
                          ? "bg-green-900/30 border-green-500/50"
                          : needsResolve
                            ? "bg-amber-900/30 border-amber-500/50"
                            : readyToDownload
                              ? "bg-blue-900/20 border-blue-500/30"
                              : "bg-slate-dark border-slate-mid"
                    )}
                  >
                    {/* Main row */}
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-3 flex-1 min-w-0">
                        {/* Status icon */}
                        {isDownloading ? (
                          <div className="w-8 h-8 rounded-full bg-synapse/30 flex items-center justify-center flex-shrink-0">
                            <Download className="w-5 h-5 text-synapse animate-pulse" />
                          </div>
                        ) : isInstalled ? (
                          <div className="w-8 h-8 rounded-full bg-green-500/30 flex items-center justify-center flex-shrink-0">
                            <Check className="w-5 h-5 text-green-400" />
                          </div>
                        ) : needsResolve ? (
                          <div className="w-8 h-8 rounded-full bg-amber-500/30 flex items-center justify-center flex-shrink-0">
                            <AlertTriangle className="w-5 h-5 text-amber-400" />
                          </div>
                        ) : (
                          <div className="w-8 h-8 rounded-full bg-blue-500/20 flex items-center justify-center flex-shrink-0">
                            <Package className="w-5 h-5 text-blue-400" />
                          </div>
                        )}

                        <div className="min-w-0 flex-1">
                          <div className="flex items-center gap-2">
                            <p className="text-text-primary font-medium truncate">{asset.name}</p>
                            {asset.version_name && (
                              <span className="px-1.5 py-0.5 bg-slate-mid/50 text-text-muted rounded text-xs">
                                v{asset.version_name}
                              </span>
                            )}
                          </div>
                          <div className="flex items-center gap-2 text-xs text-text-muted">
                            <span className="uppercase font-medium">{asset.asset_type}</span>
                            <span>•</span>
                            <span>{asset.source}</span>
                            {asset.base_model_hint && (
                              <>
                                <span>•</span>
                                <span className="text-amber-400 font-medium">{asset.base_model_hint}</span>
                              </>
                            )}
                            {asset.size && (
                              <>
                                <span>•</span>
                                <span>{formatSize(asset.size)}</span>
                              </>
                            )}
                          </div>
                          {/* Show description for base model or when available */}
                          {asset.description && (
                            <p className="text-xs text-amber-400/80 mt-1 italic">
                              {asset.description}
                            </p>
                          )}
                        </div>
                      </div>

                      {/* Actions */}
                      <div className="flex items-center gap-2 flex-shrink-0">
                        {/* Download button for assets with URL that are not installed */}
                        {canDownload && !isDownloading && (
                          <button
                            onClick={() => {
                              console.log('[PackDetailPage] Download clicked:', asset.name, asset.url)
                              downloadAssetMutation.mutate(asset)
                            }}
                            className="p-2 bg-synapse text-white rounded-lg hover:bg-synapse/80 transition-colors"
                            title="Download"
                          >
                            <Download className="w-4 h-4" />
                          </button>
                        )}

                        {/* Downloading spinner */}
                        {isDownloading && !assetDownload && (
                          <Loader2 className="w-5 h-5 text-synapse animate-spin" />
                        )}

                        {/* Select button for unresolved base model or missing URL */}
                        {isBaseModel && !isInstalled && !canDownload && (
                          <button
                            onClick={() => setShowBaseModelResolver(true)}
                            className="px-3 py-1.5 bg-amber-500/30 text-amber-300 rounded-lg text-sm font-medium hover:bg-amber-500/40 transition-colors"
                          >
                            Select Model
                          </button>
                        )}

                        {/* Change base model button (only show if INSTALLED) */}
                        {isBaseModel && isInstalled && !needsResolve && (
                          <button
                            onClick={() => setShowBaseModelResolver(true)}
                            className="p-2 bg-slate-mid text-text-muted rounded-lg hover:text-amber-400 hover:bg-slate-mid/80 transition-colors"
                            title="Change base model"
                          >
                            <ArrowLeftRight className="w-4 h-4" />
                          </button>
                        )}

                        {/* Reload/Re-download button for installed assets */}
                        {isInstalled && (
                          <button
                            onClick={() => {
                              if (confirm(`Re-download ${asset.filename || asset.name}? This will replace the existing file.`)) {
                                console.log('[PackDetailPage] Re-download asset:', asset.name)
                                downloadAssetMutation.mutate(asset)
                              }
                            }}
                            className="p-2 bg-slate-mid text-text-muted rounded-lg hover:text-synapse hover:bg-slate-mid/80 transition-colors"
                            title="Re-download"
                          >
                            <RotateCcw className="w-4 h-4" />
                          </button>
                        )}

                        {/* Delete button for installed assets */}
                        {isInstalled && (
                          <button
                            onClick={() => {
                              const deleteChoice = confirm(
                                `Delete downloaded file for "${asset.filename || asset.name}"?\n\n` +
                                `This will remove the file from blob store.\n\n` +
                                `Press OK to delete file only.\n` +
                                `The dependency will remain in pack.json for re-download.`
                              )
                              if (deleteChoice) {
                                console.log('[PackDetailPage] Delete resource:', asset.name)
                                deleteResourceMutation.mutate({ depId: asset.name, deleteDependency: false })
                              }
                            }}
                            disabled={deleteResourceMutation.isPending}
                            className="p-2 bg-red-500/20 text-red-400 rounded-lg hover:bg-red-500/30 transition-colors"
                            title="Delete downloaded file"
                          >
                            {deleteResourceMutation.isPending ? (
                              <Loader2 className="w-4 h-4 animate-spin" />
                            ) : (
                              <Trash2 className="w-4 h-4" />
                            )}
                          </button>
                        )}
                      </div>
                    </div>

                    {/* Inline download progress */}
                    {assetDownload && assetDownload.status === 'downloading' && (
                      <div className="mt-3 space-y-2">
                        <ProgressBar progress={assetDownload.progress} showLabel={true} />
                        <div className="flex items-center justify-between text-xs text-text-muted">
                          <div className="flex items-center gap-3">
                            <span className="flex items-center gap-1">
                              <HardDrive className="w-3 h-3" />
                              {formatBytes(assetDownload.downloaded_bytes)} / {formatBytes(assetDownload.total_bytes)}
                            </span>
                            <span className="flex items-center gap-1">
                              <Gauge className="w-3 h-3" />
                              {formatSpeed(assetDownload.speed_bps)}
                            </span>
                          </div>
                          <span className="flex items-center gap-1">
                            <Timer className="w-3 h-3" />
                            ETA: {formatEta(assetDownload.eta_seconds)}
                          </span>
                        </div>
                      </div>
                    )}

                    {/* File info row - Extended details */}
                    <div className="mt-3 pt-3 border-t border-white/10 text-xs space-y-1.5">
                      {/* File name */}
                      {asset.filename && (
                        <div className="flex items-center gap-2 text-text-muted">
                          <span className="font-medium text-text-secondary w-16">File:</span>
                          <code className="bg-slate-mid/50 px-2 py-0.5 rounded flex-1 truncate">{asset.filename}</code>
                        </div>
                      )}

                      {/* Version */}
                      {asset.version_name && (
                        <div className="flex items-center gap-2 text-text-muted">
                          <span className="font-medium text-text-secondary w-16">Version:</span>
                          <span className="text-synapse">{asset.version_name}</span>
                        </div>
                      )}

                      {/* Source info */}
                      {asset.source_info && (
                        <>
                          {asset.source_info.model_name && (
                            <div className="flex items-center gap-2 text-text-muted">
                              <span className="font-medium text-text-secondary w-16">Model:</span>
                              <span>{asset.source_info.model_name}</span>
                              {asset.source_info.model_id && (
                                <span className="text-text-muted/60">(#{asset.source_info.model_id})</span>
                              )}
                            </div>
                          )}
                          {asset.source_info.creator && (
                            <div className="flex items-center gap-2 text-text-muted">
                              <span className="font-medium text-text-secondary w-16">Creator:</span>
                              <span className="text-blue-400">{asset.source_info.creator}</span>
                            </div>
                          )}
                          {asset.source_info.repo_id && (
                            <div className="flex items-center gap-2 text-text-muted">
                              <span className="font-medium text-text-secondary w-16">Repo:</span>
                              <span>{asset.source_info.repo_id}</span>
                            </div>
                          )}
                        </>
                      )}

                      {/* Size */}
                      {asset.size && (
                        <div className="flex items-center gap-2 text-text-muted">
                          <span className="font-medium text-text-secondary w-16">Size:</span>
                          <span>{formatBytes(asset.size)}</span>
                        </div>
                      )}

                      {/* SHA256 */}
                      {asset.sha256 && (
                        <div className="flex items-center gap-2 text-text-muted">
                          <span className="font-medium text-text-secondary w-16">SHA256:</span>
                          <code className="truncate flex-1 text-green-400/70" title={asset.sha256}>
                            {asset.sha256.substring(0, 16)}...
                          </code>
                        </div>
                      )}

                      {/* Download URL */}
                      {asset.url && !isInstalled && (
                        <div className="flex items-center gap-2 text-text-muted">
                          <span className="font-medium text-text-secondary w-16">URL:</span>
                          <a
                            href={asset.url}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="truncate flex-1 text-blue-400 hover:underline"
                            title={asset.url}
                          >
                            {asset.url.length > 60 ? asset.url.substring(0, 60) + '...' : asset.url}
                          </a>
                        </div>
                      )}

                      {/* Local path */}
                      {asset.local_path && (
                        <div className="flex items-center gap-2 text-text-muted">
                          <FolderOpen className="w-3 h-3 text-text-secondary" />
                          <span className="font-medium text-text-secondary">Path:</span>
                          <code className="truncate flex-1" title={asset.local_path}>{asset.local_path}</code>
                        </div>
                      )}
                      {!asset.local_path && asset.url && !isDownloading && (
                        <div className="flex items-center gap-2 text-text-muted">
                          <Globe className="w-3 h-3" />
                          <span className="truncate flex-1" title={asset.url}>Ready to download</span>
                        </div>
                      )}

                    </div>
                  </div>
                )
              })}
            </div>
          ) : (
            <p className="text-text-muted text-sm">No dependencies</p>
          )
        }
      </Card >

      {/* ComfyUI Workflows */}
      < Card className="p-4" >
        <div className="flex items-center justify-between mb-3">
          <h3 className="text-sm font-semibold text-text-primary flex items-center gap-2">
            <FileJson className="w-4 h-4" />
            ComfyUI Workflows ({pack.workflows?.length || 0})
          </h3>
          <div className="flex items-center gap-2">
            <Button
              size="sm"
              variant="secondary"
              onClick={() => {
                setUploadWorkflowFile(null)
                setUploadWorkflowName('')
                setUploadWorkflowDescription('')
                setShowUploadWorkflowModal(true)
              }}
            >
              <Download className="w-4 h-4 rotate-180" />
              Upload
            </Button>
            <div className="relative group">
              <Button
                size="sm"
                variant="primary"
                disabled={needsBaseModel || generateWorkflowMutation.isPending}
                onClick={() => generateWorkflowMutation.mutate()}
                className={needsBaseModel ? 'opacity-50 cursor-not-allowed' : ''}
              >
                {generateWorkflowMutation.isPending ? (
                  <Loader2 className="w-4 h-4 animate-spin" />
                ) : (
                  <Play className="w-4 h-4" />
                )}
                Generate Default
              </Button>
              {needsBaseModel && (
                <div className="absolute bottom-full left-1/2 -translate-x-1/2 mb-2 px-3 py-2 bg-slate-dark border border-amber-500/50 rounded-lg text-xs text-amber-400 whitespace-nowrap opacity-0 group-hover:opacity-100 transition-opacity pointer-events-none">
                  ⚠️ Resolve all models before generating workflow
                </div>
              )}
            </div>
          </div>
        </div>

        {
          pack.workflows?.length > 0 ? (
            <div className="space-y-2">
              {pack.workflows.map((workflow, idx) => {
                // Data now comes directly from API response
                const hasSymlink = workflow.has_symlink || false
                const symlinkValid = workflow.symlink_valid || false

                return (
                  <div
                    key={idx}
                    className={clsx(
                      "flex items-center justify-between p-3 rounded-lg border",
                      hasSymlink && symlinkValid
                        ? "bg-green-500/10 border-green-500/30"
                        : "bg-slate-dark border-slate-mid/30"
                    )}
                  >
                    <div className="flex items-center gap-3">
                      <FileJson className={clsx(
                        "w-5 h-5",
                        hasSymlink && symlinkValid ? "text-green-400" : "text-synapse"
                      )} />
                      <div>
                        <p className="text-text-primary font-medium">{workflow.name}</p>
                        <div className="flex items-center gap-2 text-xs text-text-muted">
                          <span>{workflow.filename}</span>
                          {workflow.is_default && (
                            <span className="px-1.5 py-0.5 bg-synapse/20 text-synapse rounded">default</span>
                          )}
                          {hasSymlink && symlinkValid && (
                            <span className="px-1.5 py-0.5 bg-green-500/20 text-green-400 rounded flex items-center gap-1">
                              <Check className="w-3 h-3" />
                              In ComfyUI
                            </span>
                          )}
                          {hasSymlink && !symlinkValid && (
                            <span className="px-1.5 py-0.5 bg-orange-500/20 text-orange-400 rounded flex items-center gap-1">
                              <AlertTriangle className="w-3 h-3" />
                              Broken link
                            </span>
                          )}
                        </div>
                        {/* Show local path */}
                        {workflow.local_path && (
                          <p className="text-xs text-text-muted mt-1 font-mono truncate max-w-md" title={workflow.local_path}>
                            {workflow.local_path}
                          </p>
                        )}
                        {workflow.description && (
                          <p className="text-xs text-text-muted mt-1">{workflow.description}</p>
                        )}
                      </div>
                    </div>

                    <div className="flex items-center gap-2">
                      {/* Link/Unlink to ComfyUI */}
                      {hasSymlink ? (
                        <button
                          onClick={() => {
                            if (confirm('Remove workflow from ComfyUI?')) {
                              removeSymlinkMutation.mutate(workflow.filename)
                            }
                          }}
                          disabled={removeSymlinkMutation.isPending}
                          className="px-3 py-1.5 bg-slate-mid/50 text-text-secondary rounded-lg text-sm hover:bg-slate-mid transition-colors flex items-center gap-1.5"
                          title="Remove from ComfyUI"
                        >
                          {removeSymlinkMutation.isPending ? (
                            <Loader2 className="w-4 h-4 animate-spin" />
                          ) : (
                            <X className="w-4 h-4" />
                          )}
                          Unlink
                        </button>
                      ) : (
                        <button
                          onClick={() => createSymlinkMutation.mutate(workflow.filename)}
                          disabled={createSymlinkMutation.isPending}
                          className="px-3 py-1.5 bg-synapse/20 text-synapse rounded-lg text-sm hover:bg-synapse/30 transition-colors flex items-center gap-1.5"
                          title="Add to ComfyUI workflows"
                        >
                          {createSymlinkMutation.isPending ? (
                            <Loader2 className="w-4 h-4 animate-spin" />
                          ) : (
                            <FolderOpen className="w-4 h-4" />
                          )}
                          Link to ComfyUI
                        </button>
                      )}

                      {/* Download workflow JSON */}
                      <button
                        onClick={() => {
                          window.open(`/api/packs/${encodeURIComponent(packName)}/workflow/${encodeURIComponent(workflow.filename)}`, '_blank')
                        }}
                        className="p-1.5 bg-slate-mid/50 text-text-secondary rounded-lg hover:bg-slate-mid transition-colors"
                        title="Download workflow JSON"
                      >
                        <Download className="w-4 h-4" />
                      </button>

                      {/* Delete workflow */}
                      <button
                        onClick={() => {
                          if (confirm(`Delete workflow "${workflow.name}"?`)) {
                            deleteWorkflowMutation.mutate(workflow.filename)
                          }
                        }}
                        disabled={deleteWorkflowMutation.isPending}
                        className="p-1.5 bg-red-500/20 text-red-400 rounded-lg hover:bg-red-500/30 transition-colors"
                        title="Delete workflow"
                      >
                        {deleteWorkflowMutation.isPending ? (
                          <Loader2 className="w-4 h-4 animate-spin" />
                        ) : (
                          <Trash2 className="w-4 h-4" />
                        )}
                      </button>
                    </div>
                  </div>
                )
              })}
            </div>
          ) : (
            <div className="text-center py-8 text-text-muted">
              <FileJson className="w-12 h-12 mx-auto mb-3 opacity-50" />
              <p className="text-sm">No workflows yet</p>
              <p className="text-xs mt-1">
                Click "Generate Default" to create one based on pack configuration,
                <br />or "Upload" to add an existing workflow.
              </p>
            </div>
          )
        }
      </Card >

      {/* Upload Workflow Modal */}
      {
        showUploadWorkflowModal && (
          <div className="fixed inset-0 bg-black/70 flex items-center justify-center z-50 p-4">
            <div className="bg-slate-deep rounded-2xl p-6 max-w-lg w-full border border-slate-mid/50">
              <h3 className="text-lg font-semibold text-text-primary mb-4">Upload Workflow</h3>

              <div className="space-y-4">
                {/* File input */}
                <div>
                  <label className="block text-sm text-text-secondary mb-1">Workflow File (.json)</label>
                  <input
                    type="file"
                    accept=".json"
                    onChange={(e) => {
                      const file = e.target.files?.[0]
                      if (file) {
                        setUploadWorkflowFile(file)
                        if (!uploadWorkflowName) {
                          setUploadWorkflowName(file.name.replace('.json', ''))
                        }
                      }
                    }}
                    className="w-full px-3 py-2 bg-slate-dark rounded-lg border border-slate-mid text-text-primary file:mr-4 file:py-1 file:px-3 file:rounded file:border-0 file:bg-synapse/20 file:text-synapse file:cursor-pointer"
                  />
                </div>

                {/* Name */}
                <div>
                  <label className="block text-sm text-text-secondary mb-1">Workflow Name</label>
                  <input
                    type="text"
                    value={uploadWorkflowName}
                    onChange={(e) => setUploadWorkflowName(e.target.value)}
                    placeholder="My Custom Workflow"
                    className="w-full px-3 py-2 bg-slate-dark rounded-lg border border-slate-mid text-text-primary placeholder:text-text-muted"
                  />
                </div>

                {/* Description */}
                <div>
                  <label className="block text-sm text-text-secondary mb-1">Description (optional)</label>
                  <textarea
                    value={uploadWorkflowDescription}
                    onChange={(e) => setUploadWorkflowDescription(e.target.value)}
                    placeholder="Describe what this workflow does..."
                    rows={2}
                    className="w-full px-3 py-2 bg-slate-dark rounded-lg border border-slate-mid text-text-primary placeholder:text-text-muted resize-none"
                  />
                </div>
              </div>

              <div className="flex justify-end gap-3 mt-6">
                <Button
                  variant="secondary"
                  onClick={() => setShowUploadWorkflowModal(false)}
                >
                  Cancel
                </Button>
                <Button
                  variant="primary"
                  disabled={!uploadWorkflowFile || !uploadWorkflowName || uploadWorkflowMutation.isPending}
                  onClick={() => {
                    if (uploadWorkflowFile && uploadWorkflowName) {
                      uploadWorkflowMutation.mutate({
                        file: uploadWorkflowFile,
                        name: uploadWorkflowName,
                        description: uploadWorkflowDescription || undefined,
                      })
                    }
                  }}
                >
                  {uploadWorkflowMutation.isPending ? (
                    <Loader2 className="w-4 h-4 animate-spin" />
                  ) : (
                    <Download className="w-4 h-4 rotate-180" />
                  )}
                  Upload
                </Button>
              </div>
            </div>
          </div>
        )
      }

      {/* Actions */}
      <div className="flex gap-3">
        <Button
          variant="secondary"
          onClick={() => {
            setEditUserTags(pack.user_tags || [])
            setShowEditModal(true)
          }}
        >
          <Edit3 className="w-5 h-5" />
          Edit Pack
        </Button>
        <Button
          variant="danger"
          onClick={() => {
            if (confirm('Are you sure you want to delete this pack?')) {
              deleteMutation.mutate()
            }
          }}
          disabled={deleteMutation.isPending}
        >
          {deleteMutation.isPending ? (
            <Loader2 className="w-5 h-5 animate-spin" />
          ) : (
            <Trash2 className="w-5 h-5" />
          )}
          Delete
        </Button>
      </div>

      {/* Edit Modal */}
      {
        showEditModal && (
          <div className="fixed inset-0 bg-black/80 backdrop-blur-sm z-[80] flex items-center justify-center p-4">
            <div className="bg-slate-dark rounded-2xl p-6 max-w-lg w-full border border-slate-mid">
              <div className="flex items-center justify-between mb-6">
                <h2 className="text-xl font-bold text-text-primary">Edit Pack</h2>
                <button
                  onClick={() => setShowEditModal(false)}
                  className="p-2 hover:bg-slate-mid rounded-lg transition-colors"
                >
                  <X className="w-5 h-5 text-text-muted" />
                </button>
              </div>

              {/* User Tags Editor */}
              <div className="space-y-4">
                <div>
                  <label className="block text-sm font-medium text-text-primary mb-2">User Tags</label>
                  <div className="flex flex-wrap gap-2 mb-3">
                    {editUserTags.map((tag, idx) => (
                      <span
                        key={idx}
                        className={clsx(
                          "px-3 py-1 rounded-lg text-sm flex items-center gap-2",
                          tag === 'nsfw-pack' ? "bg-red-500/20 text-red-400" : "bg-pulse/20 text-pulse"
                        )}
                      >
                        {tag}
                        <button
                          onClick={() => setEditUserTags(prev => prev.filter((_, i) => i !== idx))}
                          className="hover:text-red-400 transition-colors"
                        >
                          <X className="w-3 h-3" />
                        </button>
                      </span>
                    ))}
                  </div>

                  {/* Suggested tags */}
                  <div className="mb-3">
                    <p className="text-xs text-text-muted mb-2">Suggested tags:</p>
                    <div className="flex flex-wrap gap-2">
                      {['favorite', 'nsfw-pack', 'anime', 'realistic', 'style', 'character'].map(suggested => (
                        <button
                          key={suggested}
                          onClick={() => {
                            if (!editUserTags.includes(suggested)) {
                              setEditUserTags(prev => [...prev, suggested])
                            }
                          }}
                          disabled={editUserTags.includes(suggested)}
                          className={clsx(
                            "px-2 py-0.5 rounded text-xs transition-colors",
                            editUserTags.includes(suggested)
                              ? "bg-slate-mid/30 text-text-muted cursor-not-allowed"
                              : suggested === 'nsfw-pack'
                                ? "bg-red-500/10 text-red-400 hover:bg-red-500/20"
                                : "bg-slate-mid/50 text-text-secondary hover:bg-slate-mid"
                          )}
                        >
                          + {suggested}
                        </button>
                      ))}
                    </div>
                  </div>

                  <div className="flex gap-2">
                    <input
                      type="text"
                      value={newTag}
                      onChange={(e) => setNewTag(e.target.value)}
                      onKeyDown={(e) => {
                        if (e.key === 'Enter' && newTag.trim()) {
                          e.preventDefault()
                          if (!editUserTags.includes(newTag.trim())) {
                            setEditUserTags(prev => [...prev, newTag.trim()])
                          }
                          setNewTag('')
                        }
                      }}
                      placeholder="Add tag and press Enter"
                      className="flex-1 px-4 py-2 bg-obsidian border border-slate-mid rounded-lg text-text-primary placeholder:text-text-muted focus:outline-none focus:border-synapse"
                    />
                    <Button
                      onClick={() => {
                        if (newTag.trim() && !editUserTags.includes(newTag.trim())) {
                          setEditUserTags(prev => [...prev, newTag.trim()])
                          setNewTag('')
                        }
                      }}
                      disabled={!newTag.trim()}
                    >
                      Add
                    </Button>
                  </div>
                </div>
              </div>

              {/* Actions */}
              <div className="flex gap-3 mt-6">
                <Button
                  variant="secondary"
                  className="flex-1"
                  onClick={() => setShowEditModal(false)}
                >
                  Cancel
                </Button>
                <Button
                  className="flex-1"
                  onClick={() => updatePackMutation.mutate({ user_tags: editUserTags })}
                  disabled={updatePackMutation.isPending}
                >
                  {updatePackMutation.isPending ? (
                    <Loader2 className="w-5 h-5 animate-spin" />
                  ) : (
                    'Save Changes'
                  )}
                </Button>
              </div>
            </div>
          </div>
        )
      }

      {/* Parameters Edit Modal */}
      {
        showParametersModal && (
          <div className="fixed inset-0 bg-black/80 backdrop-blur-sm z-[80] flex items-center justify-center p-4">
            <div className="bg-slate-dark rounded-2xl p-6 max-w-2xl w-full border border-slate-mid max-h-[85vh] overflow-hidden flex flex-col">
              <div className="flex items-center justify-between mb-4">
                <h2 className="text-xl font-bold text-text-primary">Edit Generation Parameters</h2>
                <button
                  onClick={() => setShowParametersModal(false)}
                  className="p-2 hover:bg-slate-mid rounded-lg transition-colors"
                >
                  <X className="w-5 h-5 text-text-muted" />
                </button>
              </div>

              {/* Quick add suggestions */}
              <div className="mb-4">
                <p className="text-xs text-text-muted mb-2">Quick add:</p>
                <div className="flex flex-wrap gap-2">
                  {['clipSkip', 'cfgScale', 'steps', 'sampler', 'scheduler', 'strength', 'width', 'height', 'denoise', 'seed'].map(key => (
                    !editParameters[key] && (
                      <button
                        key={key}
                        onClick={() => {
                          const defaults: Record<string, string> = {
                            clipSkip: '2',
                            cfgScale: '7',
                            steps: '20',
                            sampler: 'euler',
                            scheduler: 'normal',
                            strength: '1.0',
                            width: '512',
                            height: '512',
                            denoise: '1.0',
                            seed: '-1',
                          }
                          setEditParameters(prev => ({ ...prev, [key]: defaults[key] || '' }))
                        }}
                        className="px-3 py-1.5 text-xs bg-synapse/20 hover:bg-synapse/30 text-synapse rounded-lg transition-colors font-medium"
                      >
                        + {key}
                      </button>
                    )
                  ))}
                </div>
              </div>

              {/* Parameters list */}
              <div className="flex-1 overflow-y-auto space-y-2 mb-4 min-h-[150px]">
                {Object.entries(editParameters).length === 0 ? (
                  <p className="text-sm text-text-muted text-center py-8">No parameters set. Click quick add buttons above or add custom below.</p>
                ) : (
                  Object.entries(editParameters).map(([key, value]) => (
                    <div key={key} className="flex items-center gap-3 bg-obsidian/50 p-3 rounded-lg">
                      <span className="text-sm text-synapse font-mono min-w-[120px] font-medium">{key}</span>
                      <input
                        type="text"
                        value={value}
                        onChange={(e) => setEditParameters(prev => ({ ...prev, [key]: e.target.value }))}
                        className="flex-1 px-3 py-2 bg-obsidian border border-slate-mid rounded-lg text-text-primary text-sm focus:outline-none focus:border-synapse"
                      />
                      <button
                        onClick={() => {
                          const newParams = { ...editParameters }
                          delete newParams[key]
                          setEditParameters(newParams)
                        }}
                        className="p-1.5 hover:bg-red-500/20 rounded transition-colors"
                        title="Remove parameter"
                      >
                        <X className="w-4 h-4 text-red-400" />
                      </button>
                    </div>
                  ))
                )}
              </div>

              {/* Add new parameter */}
              <div className="border-t border-slate-mid pt-4 mb-4">
                <p className="text-xs text-text-muted mb-3">Add custom parameter:</p>
                <div className="flex flex-col sm:flex-row gap-2">
                  <input
                    type="text"
                    placeholder="Parameter name (e.g. clipSkip)"
                    value={newParamKey}
                    onChange={(e) => setNewParamKey(e.target.value)}
                    className="flex-1 px-3 py-2.5 bg-obsidian border border-slate-mid rounded-lg text-text-primary text-sm focus:outline-none focus:border-synapse"
                  />
                  <input
                    type="text"
                    placeholder="Value"
                    value={newParamValue}
                    onChange={(e) => setNewParamValue(e.target.value)}
                    className="flex-1 px-3 py-2.5 bg-obsidian border border-slate-mid rounded-lg text-text-primary text-sm focus:outline-none focus:border-synapse"
                  />
                  <button
                    onClick={() => {
                      if (newParamKey.trim()) {
                        setEditParameters(prev => ({ ...prev, [newParamKey.trim()]: newParamValue }))
                        setNewParamKey('')
                        setNewParamValue('')
                      }
                    }}
                    disabled={!newParamKey.trim()}
                    className="px-6 py-2.5 bg-synapse hover:bg-synapse/80 disabled:bg-slate-mid disabled:text-text-muted text-obsidian font-semibold rounded-lg transition-colors whitespace-nowrap"
                  >
                    + Add
                  </button>
                </div>
              </div>

              <div className="flex gap-3 pt-2">
                <Button
                  variant="secondary"
                  className="flex-1"
                  onClick={() => setShowParametersModal(false)}
                >
                  Cancel
                </Button>
                <Button
                  className="flex-1"
                  onClick={() => {
                    // Convert parameters to proper types
                    const params: Record<string, unknown> = {}
                    for (const [key, value] of Object.entries(editParameters)) {
                      if (value === '') continue
                      // Try to parse as number
                      const numValue = parseFloat(value)
                      if (!isNaN(numValue) && key !== 'sampler') {
                        params[key] = numValue
                      } else {
                        params[key] = value
                      }
                    }
                    updateParametersMutation.mutate(params)
                  }}
                  disabled={updateParametersMutation.isPending}
                >
                  {updateParametersMutation.isPending ? (
                    <Loader2 className="w-5 h-5 animate-spin" />
                  ) : (
                    'Save'
                  )}
                </Button>
              </div>
            </div>
          </div>
        )
      }
    </div >
  )
}
