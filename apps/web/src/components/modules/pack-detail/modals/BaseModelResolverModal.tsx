/**
 * BaseModelResolverModal
 *
 * Complex modal for resolving base model dependencies.
 * Supports three sources: Local (ComfyUI), Civitai, HuggingFace.
 *
 * FUNKCE ZACHOVÁNY:
 * - Tab navigation (local/civitai/huggingface)
 * - Smart base model hint detection
 * - Local model filtering
 * - Remote search with method info
 * - HuggingFace file selection
 * - Model selection and resolution
 *
 * VIZUÁLNĚ VYLEPŠENO:
 * - Premium modal design
 * - Enhanced tab styling
 * - Better result cards
 * - Improved loading states
 */

import { useState, useEffect, useMemo } from 'react'
import {
  X,
  Loader2,
  Check,
  Search,
  HardDrive,
  Globe,
  Database,
  Package,
  AlertTriangle,
  ChevronRight,
  ChevronDown,
} from 'lucide-react'
import { clsx } from 'clsx'
import { Button } from '@/components/ui/Button'
import type {
  LocalModel,
  BaseModelResult,
  BaseModelSearchResponse,
  HuggingFaceFile,
  ResolverTab,
} from '../types'
import { ANIMATION_PRESETS } from '../constants'
import { formatSize } from '../utils'

// =============================================================================
// Types
// =============================================================================

export interface BaseModelResolverModalProps {
  /**
   * Whether modal is open
   */
  isOpen: boolean

  /**
   * Pack description for base model hint extraction
   */
  packDescription?: string

  /**
   * Local models from ComfyUI
   */
  localModels: LocalModel[]

  /**
   * Whether local models are loading
   */
  isLoadingLocalModels?: boolean

  /**
   * Search results from remote sources
   */
  searchResponse?: BaseModelSearchResponse

  /**
   * Whether search is in progress
   */
  isSearching?: boolean

  /**
   * Handler for search action
   */
  onSearch: (query: string, source: 'civitai' | 'huggingface') => void

  /**
   * Handler for fetching HuggingFace files
   */
  onFetchHfFiles: (repoId: string) => Promise<HuggingFaceFile[]>

  /**
   * Handler for resolve action
   */
  onResolve: (data: {
    model_path?: string
    download_url?: string
    source?: string
    file_name?: string
    size_kb?: number
  }) => void

  /**
   * Handler for close/cancel
   */
  onClose: () => void

  /**
   * Whether resolve is in progress
   */
  isResolving?: boolean
}

// =============================================================================
// Helper Functions
// =============================================================================

/**
 * Extract base model hint from description
 */
function extractBaseModelHint(description?: string): string | null {
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

// =============================================================================
// Sub-components
// =============================================================================

interface TabButtonProps {
  tab: ResolverTab
  currentTab: ResolverTab
  onClick: () => void
  icon: React.ReactNode
  label: string
}

function TabButton({ tab, currentTab, onClick, icon, label }: TabButtonProps) {
  const isActive = tab === currentTab

  return (
    <button
      onClick={onClick}
      className={clsx(
        "flex-1 flex items-center justify-center gap-2 py-3 px-4",
        "transition-all duration-200 font-medium",
        isActive
          ? "text-synapse border-b-2 border-synapse bg-synapse/10"
          : "text-text-muted hover:text-text-primary hover:bg-slate-mid/30"
      )}
    >
      {icon}
      {label}
    </button>
  )
}

interface LocalModelCardProps {
  model: LocalModel
  isSelected: boolean
  onSelect: () => void
}

function LocalModelCard({ model, isSelected, onSelect }: LocalModelCardProps) {
  return (
    <button
      onClick={onSelect}
      className={clsx(
        "w-full text-left p-4 rounded-xl",
        "transition-all duration-200",
        "flex items-center gap-3",
        isSelected
          ? "bg-synapse/20 border-2 border-synapse"
          : "bg-slate-dark border border-slate-mid hover:border-slate-mid/80"
      )}
    >
      <Package className={clsx(
        "w-6 h-6 flex-shrink-0",
        isSelected ? "text-synapse" : "text-text-muted"
      )} />
      <div className="min-w-0 flex-1">
        <p className="text-text-primary font-medium truncate">{model.name}</p>
        <p className="text-xs text-text-muted truncate">{model.path}</p>
        {model.size && (
          <p className="text-xs text-text-muted mt-0.5">{formatSize(model.size)}</p>
        )}
      </div>
      {isSelected && (
        <Check className="w-5 h-5 text-synapse flex-shrink-0" />
      )}
    </button>
  )
}

interface RemoteModelCardProps {
  model: BaseModelResult
  isSelected: boolean
  onSelect: () => void
}

function RemoteModelCard({ model, isSelected, onSelect }: RemoteModelCardProps) {
  return (
    <button
      onClick={onSelect}
      className={clsx(
        "w-full text-left p-4 rounded-xl",
        "transition-all duration-200",
        isSelected
          ? "bg-synapse/20 border-2 border-synapse"
          : "bg-slate-dark border border-slate-mid hover:border-slate-mid/80"
      )}
    >
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0 flex-1">
          <p className="text-text-primary font-medium">{model.model_name}</p>
          {model.version_name && (
            <p className="text-sm text-synapse">{model.version_name}</p>
          )}
          {model.creator && (
            <p className="text-xs text-text-muted">by {model.creator}</p>
          )}
          <div className="flex items-center gap-2 mt-2 flex-wrap">
            {model.base_model && (
              <span className="px-2 py-0.5 bg-pulse/20 text-pulse text-xs rounded">
                {model.base_model}
              </span>
            )}
            {model.size_gb && (
              <span className="text-xs text-text-muted">
                {model.size_gb.toFixed(1)} GB
              </span>
            )}
            <span className="text-xs text-text-muted">
              {model.download_count.toLocaleString()} downloads
            </span>
          </div>
          <p className="text-xs text-text-muted mt-1 font-mono truncate">
            {model.file_name}
          </p>
        </div>
        {isSelected && (
          <Check className="w-5 h-5 text-synapse flex-shrink-0" />
        )}
      </div>
    </button>
  )
}

interface HuggingFaceModelCardProps {
  model: BaseModelResult
  isExpanded: boolean
  isSelected: boolean
  files: HuggingFaceFile[]
  isLoadingFiles: boolean
  selectedFile?: HuggingFaceFile
  onToggleExpand: () => void
  onSelectFile: (file: HuggingFaceFile) => void
}

function HuggingFaceModelCard({
  model,
  isExpanded,
  isSelected,
  files,
  isLoadingFiles,
  selectedFile,
  onToggleExpand,
  onSelectFile,
}: HuggingFaceModelCardProps) {
  return (
    <div
      className={clsx(
        "rounded-xl overflow-hidden",
        "transition-all duration-200",
        isSelected
          ? "bg-synapse/20 border-2 border-synapse"
          : "bg-slate-dark border border-slate-mid"
      )}
    >
      {/* Header */}
      <button
        onClick={onToggleExpand}
        className="w-full text-left p-4 flex items-center justify-between"
      >
        <div className="min-w-0 flex-1">
          <p className="text-text-primary font-medium">{model.model_name}</p>
          {model.creator && (
            <p className="text-xs text-text-muted">by {model.creator}</p>
          )}
          <div className="flex items-center gap-2 mt-1">
            <span className="text-xs text-text-muted">
              {model.download_count.toLocaleString()} downloads
            </span>
          </div>
        </div>
        {isExpanded ? (
          <ChevronDown className="w-5 h-5 text-text-muted" />
        ) : (
          <ChevronRight className="w-5 h-5 text-text-muted" />
        )}
      </button>

      {/* Expanded Files List */}
      {isExpanded && (
        <div className="border-t border-slate-mid p-3 space-y-2">
          {isLoadingFiles ? (
            <div className="flex items-center justify-center py-4">
              <Loader2 className="w-5 h-5 animate-spin text-synapse" />
            </div>
          ) : files.length === 0 ? (
            <p className="text-sm text-text-muted text-center py-4">
              No compatible files found
            </p>
          ) : (
            files.map((file) => (
              <button
                key={file.filename}
                onClick={() => onSelectFile(file)}
                className={clsx(
                  "w-full text-left p-3 rounded-lg flex items-center gap-3",
                  "transition-all duration-200",
                  selectedFile?.filename === file.filename
                    ? "bg-synapse/30 border border-synapse"
                    : "bg-obsidian/50 border border-transparent hover:border-slate-mid"
                )}
              >
                <Package className="w-4 h-4 text-text-muted flex-shrink-0" />
                <div className="min-w-0 flex-1">
                  <p className="text-sm text-text-primary truncate">{file.filename}</p>
                  <p className="text-xs text-text-muted">
                    {file.size_gb?.toFixed(2) ?? formatSize(file.size_bytes)} GB
                  </p>
                </div>
                {file.is_recommended && (
                  <span className="px-2 py-0.5 bg-green-500/20 text-green-400 text-xs rounded">
                    recommended
                  </span>
                )}
                {selectedFile?.filename === file.filename && (
                  <Check className="w-4 h-4 text-synapse flex-shrink-0" />
                )}
              </button>
            ))
          )}
        </div>
      )}
    </div>
  )
}

// =============================================================================
// Main Component
// =============================================================================

export function BaseModelResolverModal({
  isOpen,
  packDescription,
  localModels,
  isLoadingLocalModels = false,
  searchResponse,
  isSearching = false,
  onSearch,
  onFetchHfFiles,
  onResolve,
  onClose,
  isResolving = false,
}: BaseModelResolverModalProps) {
  // Tab state
  const [tab, setTab] = useState<ResolverTab>('local')

  // Search state
  const [searchQuery, setSearchQuery] = useState('')
  const [searchTrigger, setSearchTrigger] = useState('')

  // Selection state
  const [selectedLocal, setSelectedLocal] = useState<LocalModel | null>(null)
  const [selectedRemote, setSelectedRemote] = useState<BaseModelResult | null>(null)

  // HuggingFace state
  const [expandedRepo, setExpandedRepo] = useState<string | null>(null)
  const [hfFiles, setHfFiles] = useState<HuggingFaceFile[]>([])
  const [isLoadingHfFiles, setIsLoadingHfFiles] = useState(false)
  const [selectedHfFile, setSelectedHfFile] = useState<HuggingFaceFile | null>(null)

  // Extract base model hint
  const baseModelHint = useMemo(
    () => extractBaseModelHint(packDescription),
    [packDescription]
  )

  // Filter local models
  const filteredLocalModels = useMemo(() => {
    if (!searchQuery) return localModels
    return localModels.filter((m) =>
      m.name.toLowerCase().includes(searchQuery.toLowerCase())
    )
  }, [localModels, searchQuery])

  // Reset state when modal opens
  useEffect(() => {
    if (isOpen) {
      setTab('local')
      setSearchQuery(baseModelHint || '')
      setSearchTrigger('')
      setSelectedLocal(null)
      setSelectedRemote(null)
      setExpandedRepo(null)
      setHfFiles([])
      setSelectedHfFile(null)
    }
  }, [isOpen, baseModelHint])

  // Trigger search when tab changes with query
  useEffect(() => {
    if (searchTrigger && (tab === 'civitai' || tab === 'huggingface')) {
      onSearch(searchTrigger, tab)
    }
  }, [searchTrigger, tab, onSearch])

  const handleSearch = () => {
    if (searchQuery.length >= 2) {
      setSearchTrigger(searchQuery)
    }
  }

  const handleExpandHfRepo = async (repoId: string) => {
    if (expandedRepo === repoId) {
      setExpandedRepo(null)
      return
    }

    setExpandedRepo(repoId)
    setIsLoadingHfFiles(true)
    setSelectedHfFile(null)

    try {
      const files = await onFetchHfFiles(repoId)
      setHfFiles(files)
      // Auto-select recommended file if available
      const recommended = files.find((f) => f.is_recommended)
      if (recommended) {
        setSelectedHfFile(recommended)
      }
    } finally {
      setIsLoadingHfFiles(false)
    }
  }

  const handleSelectLocal = (model: LocalModel) => {
    setSelectedLocal(model)
    setSelectedRemote(null)
    setSelectedHfFile(null)
  }

  const handleSelectRemote = (model: BaseModelResult) => {
    setSelectedRemote(model)
    setSelectedLocal(null)
    if (tab !== 'huggingface') {
      setSelectedHfFile(null)
    }
  }

  const handleSelectHfFile = (file: HuggingFaceFile) => {
    setSelectedHfFile(file)
  }

  const handleResolve = () => {
    if (selectedLocal) {
      onResolve({
        model_path: selectedLocal.path,
      })
    } else if (selectedRemote) {
      if (tab === 'huggingface' && selectedHfFile) {
        onResolve({
          download_url: selectedHfFile.download_url,
          source: 'huggingface',
          file_name: selectedHfFile.filename,
          size_kb: Math.round(selectedHfFile.size_bytes / 1024),
        })
      } else {
        onResolve({
          download_url: selectedRemote.download_url,
          source: selectedRemote.source,
          file_name: selectedRemote.file_name,
          size_kb: selectedRemote.size_kb,
        })
      }
    }
  }

  const canResolve = selectedLocal || (selectedRemote && (tab !== 'huggingface' || selectedHfFile))

  if (!isOpen) return null

  return (
    <div
      className={clsx(
        "fixed inset-0 bg-black/80 backdrop-blur-sm z-50",
        "flex items-center justify-center p-4",
        ANIMATION_PRESETS.fadeIn
      )}
      onClick={(e) => {
        if (e.target === e.currentTarget) onClose()
      }}
    >
      <div
        className={clsx(
          "bg-slate-deep border border-slate-mid rounded-2xl",
          "max-w-3xl w-full max-h-[85vh] overflow-hidden flex flex-col",
          "shadow-2xl",
          ANIMATION_PRESETS.scaleIn
        )}
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header with warning gradient */}
        <div className="bg-gradient-to-r from-amber-500/20 to-orange-500/20 border-b border-amber-500/30 p-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <AlertTriangle className="w-6 h-6 text-amber-400" />
              <div>
                <h2 className="text-lg font-bold text-text-primary">Resolve Base Model</h2>
                <p className="text-sm text-text-muted">
                  Select or download the base checkpoint for this pack
                </p>
              </div>
            </div>
            <button
              onClick={onClose}
              className="p-2 hover:bg-slate-dark/50 rounded-lg transition-colors"
            >
              <X className="w-5 h-5 text-text-muted" />
            </button>
          </div>

          {/* Base model hint */}
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
          <TabButton
            tab="local"
            currentTab={tab}
            onClick={() => setTab('local')}
            icon={<HardDrive className="w-4 h-4" />}
            label="Local Models"
          />
          <TabButton
            tab="civitai"
            currentTab={tab}
            onClick={() => setTab('civitai')}
            icon={<Globe className="w-4 h-4" />}
            label="Civitai"
          />
          <TabButton
            tab="huggingface"
            currentTab={tab}
            onClick={() => setTab('huggingface')}
            icon={<Database className="w-4 h-4" />}
            label="Hugging Face"
          />
        </div>

        {/* Search */}
        <div className="p-4 border-b border-slate-mid">
          <div className="flex gap-2">
            <div className="relative flex-1">
              <Search className="absolute left-4 top-1/2 -translate-y-1/2 w-5 h-5 text-text-muted" />
              <input
                type="text"
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === 'Enter' && (tab === 'civitai' || tab === 'huggingface')) {
                    handleSearch()
                  }
                }}
                placeholder={
                  tab === 'local'
                    ? 'Filter local models...'
                    : tab === 'civitai'
                      ? 'Search checkpoints (e.g. Illustrious, Pony, SDXL)...'
                      : 'Search models (e.g. stable-diffusion, sdxl, flux)...'
                }
                className={clsx(
                  "w-full pl-12 pr-4 py-3 rounded-xl",
                  "bg-slate-dark border border-slate-mid",
                  "text-text-primary placeholder:text-text-muted",
                  "focus:outline-none focus:border-synapse",
                  "transition-colors duration-200"
                )}
              />
            </div>
            {(tab === 'civitai' || tab === 'huggingface') && (
              <Button
                onClick={handleSearch}
                disabled={searchQuery.length < 2 || isSearching}
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
          {searchResponse?.search_method && (
            <p className="text-xs text-text-muted mt-2">
              Search method: {searchResponse.search_method}
              {searchResponse.total_found > 0 && ` - Found ${searchResponse.total_found} models`}
            </p>
          )}
        </div>

        {/* Content */}
        <div className="flex-1 overflow-y-auto p-4">
          {/* Local Models Tab */}
          {tab === 'local' && (
            <div className="space-y-2">
              {isLoadingLocalModels ? (
                <div className="flex items-center justify-center py-12">
                  <Loader2 className="w-8 h-8 animate-spin text-synapse" />
                </div>
              ) : filteredLocalModels.length === 0 ? (
                <p className="text-center text-text-muted py-12">
                  {searchQuery ? 'No models match your filter' : 'No local models found'}
                </p>
              ) : (
                filteredLocalModels.map((model) => (
                  <LocalModelCard
                    key={model.path}
                    model={model}
                    isSelected={selectedLocal?.path === model.path}
                    onSelect={() => handleSelectLocal(model)}
                  />
                ))
              )}
            </div>
          )}

          {/* Civitai Tab */}
          {tab === 'civitai' && (
            <div className="space-y-2">
              {!searchTrigger ? (
                <p className="text-center text-text-muted py-12">
                  Enter a search term and click Search to find models
                </p>
              ) : isSearching ? (
                <div className="flex items-center justify-center py-12">
                  <Loader2 className="w-8 h-8 animate-spin text-synapse" />
                </div>
              ) : !searchResponse?.results?.length ? (
                <p className="text-center text-text-muted py-12">
                  No results found for "{searchTrigger}"
                </p>
              ) : (
                searchResponse.results.map((model) => (
                  <RemoteModelCard
                    key={model.model_id}
                    model={model}
                    isSelected={selectedRemote?.model_id === model.model_id}
                    onSelect={() => handleSelectRemote(model)}
                  />
                ))
              )}
            </div>
          )}

          {/* HuggingFace Tab */}
          {tab === 'huggingface' && (
            <div className="space-y-2">
              {!searchTrigger ? (
                <p className="text-center text-text-muted py-12">
                  Enter a search term and click Search to find models
                </p>
              ) : isSearching ? (
                <div className="flex items-center justify-center py-12">
                  <Loader2 className="w-8 h-8 animate-spin text-synapse" />
                </div>
              ) : !searchResponse?.results?.length ? (
                <p className="text-center text-text-muted py-12">
                  No results found for "{searchTrigger}"
                </p>
              ) : (
                searchResponse.results.map((model) => (
                  <HuggingFaceModelCard
                    key={model.model_id}
                    model={model}
                    isExpanded={expandedRepo === model.model_id}
                    isSelected={selectedRemote?.model_id === model.model_id}
                    files={expandedRepo === model.model_id ? hfFiles : []}
                    isLoadingFiles={isLoadingHfFiles && expandedRepo === model.model_id}
                    selectedFile={selectedHfFile ?? undefined}
                    onToggleExpand={() => {
                      handleSelectRemote(model)
                      handleExpandHfRepo(model.model_id)
                    }}
                    onSelectFile={handleSelectHfFile}
                  />
                ))
              )}
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="p-4 border-t border-slate-mid bg-slate-dark/50 flex gap-3">
          <Button
            variant="secondary"
            onClick={onClose}
            className="flex-1"
          >
            Cancel
          </Button>
          <Button
            onClick={handleResolve}
            disabled={!canResolve || isResolving}
            className="flex-1"
          >
            {isResolving ? (
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
  )
}

export default BaseModelResolverModal
