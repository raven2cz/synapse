/**
 * EditDependenciesModal
 *
 * Modal for managing pack dependencies.
 *
 * Features:
 * - List all dependencies with details
 * - Add new dependency (search Civitai/HuggingFace/Local)
 * - Remove dependency
 * - Edit dependency constraints
 * - Support for 8+ dependencies
 */

import { useState, useMemo } from 'react'
import { useTranslation } from 'react-i18next'
import {
  X,
  Loader2,
  Plus,
  Trash2,
  Search,
  Package,
  ExternalLink,
  ChevronDown,
  ChevronUp,
  Filter,
} from 'lucide-react'
import { clsx } from 'clsx'
import { Button } from '@/components/ui/Button'
import type { AssetInfo, AssetType } from '../types'
import { ANIMATION_PRESETS, ASSET_TYPE_ICONS } from '../constants'

// =============================================================================
// Types
// =============================================================================

export interface EditDependenciesModalProps {
  /**
   * Whether modal is open
   */
  isOpen: boolean

  /**
   * Current dependencies
   */
  dependencies: AssetInfo[]

  /**
   * Handler for saving changes
   */
  onSave: (data: {
    dependencies: AssetInfo[]
    removed: string[]
    added: AssetInfo[]
  }) => void

  /**
   * Handler for close/cancel
   */
  onClose: () => void

  /**
   * Handler for searching dependencies
   */
  onSearch?: (query: string, source: 'civitai' | 'huggingface' | 'local') => Promise<AssetInfo[]>

  /**
   * Whether saving is in progress
   */
  isSaving?: boolean
}

// =============================================================================
// Dependency Item Component
// =============================================================================

interface DependencyItemProps {
  dependency: AssetInfo
  isExpanded: boolean
  isMarkedForRemoval: boolean
  onToggleExpand: () => void
  onRemove: () => void
  onRestore: () => void
}

function DependencyItem({
  dependency,
  isExpanded,
  isMarkedForRemoval,
  onToggleExpand,
  onRemove,
  onRestore,
}: DependencyItemProps) {
  const { t } = useTranslation()
  const icon = ASSET_TYPE_ICONS[dependency.asset_type as keyof typeof ASSET_TYPE_ICONS] || ASSET_TYPE_ICONS.other

  // Format size
  const formatSize = (bytes?: number) => {
    if (!bytes) return t('pack.modals.editDeps.unknownSize')
    if (bytes >= 1024 * 1024 * 1024) return `${(bytes / 1024 / 1024 / 1024).toFixed(1)} GB`
    if (bytes >= 1024 * 1024) return `${(bytes / 1024 / 1024).toFixed(1)} MB`
    return `${(bytes / 1024).toFixed(1)} KB`
  }

  return (
    <div
      className={clsx(
        'rounded-xl border transition-all duration-200',
        isMarkedForRemoval
          ? 'bg-red-500/10 border-red-500/30 opacity-60'
          : 'bg-slate-dark/50 border-slate-mid hover:border-slate-light'
      )}
    >
      {/* Main row */}
      <div
        className={clsx(
          'flex items-center gap-4 p-4 cursor-pointer',
          'transition-colors duration-200'
        )}
        onClick={onToggleExpand}
      >
        {/* Icon */}
        <div className={clsx(
          'p-2 rounded-lg',
          'bg-synapse/20 text-synapse'
        )}>
          <span className="text-lg">{icon}</span>
        </div>

        {/* Info */}
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2">
            <span className={clsx(
              'font-medium',
              isMarkedForRemoval ? 'line-through text-text-muted' : 'text-text-primary'
            )}>
              {dependency.name}
            </span>
            <span className="px-2 py-0.5 rounded text-xs bg-slate-mid text-text-muted">
              {dependency.asset_type}
            </span>
          </div>
          <div className="text-sm text-text-muted mt-0.5">
            {formatSize(dependency.size)} • {dependency.source}
          </div>
        </div>

        {/* Actions */}
        <div className="flex items-center gap-2">
          {isMarkedForRemoval ? (
            <Button
              variant="secondary"
              onClick={(e) => {
                e.stopPropagation()
                onRestore()
              }}
              className="text-synapse hover:bg-synapse/20"
            >
              {t('pack.dependencies.restore')}
            </Button>
          ) : (
            <button
              onClick={(e) => {
                e.stopPropagation()
                onRemove()
              }}
              className={clsx(
                'p-2 rounded-lg',
                'text-red-400 hover:bg-red-500/20',
                'transition-colors duration-200'
              )}
              title={t('pack.modals.editDeps.removeDep')}
            >
              <Trash2 className="w-4 h-4" />
            </button>
          )}

          {/* Expand chevron */}
          {isExpanded ? (
            <ChevronUp className="w-5 h-5 text-text-muted" />
          ) : (
            <ChevronDown className="w-5 h-5 text-text-muted" />
          )}
        </div>
      </div>

      {/* Expanded details */}
      {isExpanded && !isMarkedForRemoval && (
        <div className="px-4 pb-4 pt-2 border-t border-slate-mid/50">
          <div className="grid grid-cols-2 gap-4 text-sm">
            {dependency.version_name && (
              <div>
                <span className="text-text-muted">{t('pack.dependencies.detail.version')}</span>
                <span className="text-text-secondary ml-2">{dependency.version_name}</span>
              </div>
            )}
            {dependency.filename && (
              <div>
                <span className="text-text-muted">{t('pack.dependencies.detail.file')}</span>
                <span className="text-text-secondary ml-2 font-mono text-xs">{dependency.filename}</span>
              </div>
            )}
            {dependency.sha256 && (
              <div className="col-span-2">
                <span className="text-text-muted">{t('pack.dependencies.detail.sha256')}</span>
                <span className="text-text-secondary ml-2 font-mono text-xs">{dependency.sha256.slice(0, 16)}...</span>
              </div>
            )}
            {dependency.source_info && (
              <>
                {dependency.source_info.model_name && (
                  <div>
                    <span className="text-text-muted">{t('pack.dependencies.detail.model')}</span>
                    <span className="text-text-secondary ml-2">{dependency.source_info.model_name}</span>
                  </div>
                )}
                {dependency.source_info.creator && (
                  <div>
                    <span className="text-text-muted">{t('pack.dependencies.detail.creator')}</span>
                    <span className="text-text-secondary ml-2">{dependency.source_info.creator}</span>
                  </div>
                )}
              </>
            )}
            {dependency.url && (
              <div className="col-span-2">
                <a
                  href={dependency.url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="inline-flex items-center gap-1 text-synapse hover:underline"
                >
                  <ExternalLink className="w-3 h-3" />
                  {t('pack.modals.editDeps.viewSource')}
                </a>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  )
}

// =============================================================================
// Add Dependency Panel
// =============================================================================

interface AddDependencyPanelProps {
  onAdd: (dependency: AssetInfo) => void
  onSearch?: (query: string, source: 'civitai' | 'huggingface' | 'local') => Promise<AssetInfo[]>
}

function AddDependencyPanel({ onAdd, onSearch }: AddDependencyPanelProps) {
  const { t } = useTranslation()
  const [searchQuery, setSearchQuery] = useState('')
  const [searchSource, setSearchSource] = useState<'civitai' | 'huggingface' | 'local'>('civitai')
  const [isSearching, setIsSearching] = useState(false)
  const [searchResults, setSearchResults] = useState<AssetInfo[]>([])
  const [showResults, setShowResults] = useState(false)

  const handleSearch = async () => {
    if (!searchQuery.trim() || !onSearch) return

    setIsSearching(true)
    setShowResults(true)

    try {
      const results = await onSearch(searchQuery, searchSource)
      setSearchResults(results)
    } catch (error) {
      console.error('Search failed:', error)
      setSearchResults([])
    } finally {
      setIsSearching(false)
    }
  }

  return (
    <div className="border border-dashed border-slate-mid rounded-xl p-4">
      <h4 className="text-sm font-medium text-text-primary mb-3">
        {t('pack.modals.editDeps.addDep')}
      </h4>

      {/* Source tabs */}
      <div className="flex gap-2 mb-3">
        {(['civitai', 'huggingface', 'local'] as const).map((source) => (
          <button
            key={source}
            onClick={() => setSearchSource(source)}
            className={clsx(
              'px-3 py-1.5 rounded-lg text-xs font-medium capitalize',
              'transition-colors duration-200',
              searchSource === source
                ? 'bg-synapse/20 text-synapse border border-synapse/30'
                : 'bg-slate-mid/50 text-text-muted hover:text-text-secondary'
            )}
          >
            {source}
          </button>
        ))}
      </div>

      {/* Search input */}
      <div className="flex gap-2">
        <div className="relative flex-1">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-text-muted" />
          <input
            type="text"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && handleSearch()}
            placeholder={t('pack.modals.editDeps.searchPlaceholder', { provider: searchSource })}
            className={clsx(
              'w-full pl-9 pr-3 py-2 rounded-lg',
              'bg-slate-dark border border-slate-mid',
              'text-text-primary placeholder:text-text-muted',
              'focus:outline-none focus:border-synapse focus:ring-1 focus:ring-synapse/30',
              'transition-colors duration-200'
            )}
          />
        </div>
        <Button
          variant="primary"
          onClick={handleSearch}
          disabled={!searchQuery.trim() || isSearching || !onSearch}
        >
          {isSearching ? (
            <Loader2 className="w-4 h-4 animate-spin" />
          ) : (
            <Search className="w-4 h-4" />
          )}
          Search
        </Button>
      </div>

      {/* Search results */}
      {showResults && (
        <div className="mt-4 max-h-64 overflow-y-auto">
          {isSearching ? (
            <div className="flex items-center justify-center py-8 text-text-muted">
              <Loader2 className="w-5 h-5 animate-spin mr-2" />
              {t('pack.modals.editDeps.searching')}
            </div>
          ) : searchResults.length > 0 ? (
            <div className="space-y-2">
              {searchResults.map((result, index) => (
                <div
                  key={index}
                  className={clsx(
                    'flex items-center gap-3 p-3 rounded-lg',
                    'bg-slate-dark/50 border border-slate-mid',
                    'hover:border-synapse/50 cursor-pointer',
                    'transition-colors duration-200'
                  )}
                  onClick={() => {
                    onAdd(result)
                    setShowResults(false)
                    setSearchQuery('')
                  }}
                >
                  <div className="p-1.5 rounded bg-synapse/20 text-synapse">
                    <Package className="w-4 h-4" />
                  </div>
                  <div className="flex-1 min-w-0">
                    <div className="font-medium text-text-primary truncate">
                      {result.name}
                    </div>
                    <div className="text-xs text-text-muted">
                      {result.asset_type} • {result.source}
                    </div>
                  </div>
                  <Plus className="w-5 h-5 text-synapse" />
                </div>
              ))}
            </div>
          ) : (
            <div className="text-center py-8 text-text-muted">
              {t('pack.modals.editDeps.noResults')}
            </div>
          )}
        </div>
      )}

      {!onSearch && (
        <p className="text-xs text-text-muted mt-2">
          {t('pack.modals.editDeps.notAvailable')}
        </p>
      )}
    </div>
  )
}

// =============================================================================
// Main Component
// =============================================================================

export function EditDependenciesModal({
  isOpen,
  dependencies: initialDependencies,
  onSave,
  onClose,
  onSearch,
  isSaving = false,
}: EditDependenciesModalProps) {
  const { t } = useTranslation()
  const [dependencies, setDependencies] = useState<AssetInfo[]>(initialDependencies)
  const [removedNames, setRemovedNames] = useState<Set<string>>(new Set())
  const [addedDependencies, setAddedDependencies] = useState<AssetInfo[]>([])
  const [expandedIndex, setExpandedIndex] = useState<number | null>(null)
  const [filterType, setFilterType] = useState<AssetType | 'all'>('all')
  const [searchQuery, setSearchQuery] = useState('')

  // Filter and search dependencies
  const filteredDependencies = useMemo(() => {
    return dependencies.filter((dep) => {
      // Type filter
      if (filterType !== 'all' && dep.asset_type !== filterType) return false

      // Search filter
      if (searchQuery) {
        const query = searchQuery.toLowerCase()
        return (
          dep.name.toLowerCase().includes(query) ||
          dep.asset_type.toLowerCase().includes(query) ||
          dep.source.toLowerCase().includes(query)
        )
      }

      return true
    })
  }, [dependencies, filterType, searchQuery])

  // Get unique types for filter
  const availableTypes = useMemo(() => {
    const types = new Set(dependencies.map((d) => d.asset_type))
    return Array.from(types)
  }, [dependencies])

  // Handle remove
  const handleRemove = (name: string) => {
    setRemovedNames(new Set([...removedNames, name]))
  }

  // Handle restore
  const handleRestore = (name: string) => {
    const newRemoved = new Set(removedNames)
    newRemoved.delete(name)
    setRemovedNames(newRemoved)
  }

  // Handle add
  const handleAdd = (dependency: AssetInfo) => {
    if (dependencies.some((d) => d.name === dependency.name)) {
      // Already exists, just restore if removed
      handleRestore(dependency.name)
      return
    }
    setDependencies([...dependencies, dependency])
    setAddedDependencies([...addedDependencies, dependency])
  }

  // Handle save
  const handleSave = () => {
    const finalDeps = dependencies.filter((d) => !removedNames.has(d.name))
    onSave({
      dependencies: finalDeps,
      removed: Array.from(removedNames),
      added: addedDependencies,
    })
  }

  // Check if there are changes
  const hasChanges = removedNames.size > 0 || addedDependencies.length > 0

  if (!isOpen) return null

  return (
    <div
      className={clsx(
        "fixed inset-0 bg-black/70 z-50",
        "flex items-center justify-center p-4",
        ANIMATION_PRESETS.fadeIn
      )}
      onClick={(e) => {
        if (e.target === e.currentTarget) onClose()
      }}
    >
      <div
        className={clsx(
          "bg-slate-deep rounded-2xl max-w-3xl w-full max-h-[90vh]",
          "border border-slate-mid/50",
          "shadow-2xl flex flex-col",
          ANIMATION_PRESETS.scaleIn
        )}
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div className="flex items-center justify-between p-6 border-b border-slate-mid/50">
          <div>
            <h3 className="text-lg font-semibold text-text-primary">
              {t('pack.modals.editDeps.title')}
            </h3>
            <p className="text-sm text-text-muted mt-1">
              {dependencies.length} {t('pack.modals.editDeps.depsCount')} • {removedNames.size} {t('pack.modals.editDeps.markedForRemoval')}
            </p>
          </div>
          <button
            onClick={onClose}
            className={clsx(
              "p-2 rounded-lg",
              "hover:bg-slate-mid transition-colors duration-200"
            )}
          >
            <X className="w-5 h-5 text-text-muted" />
          </button>
        </div>

        {/* Filters */}
        <div className="flex items-center gap-4 px-6 py-3 border-b border-slate-mid/30">
          {/* Search */}
          <div className="relative flex-1">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-text-muted" />
            <input
              type="text"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              placeholder={t('pack.modals.editDeps.filterPlaceholder')}
              className={clsx(
                'w-full pl-9 pr-3 py-1.5 rounded-lg text-sm',
                'bg-slate-dark border border-slate-mid',
                'text-text-primary placeholder:text-text-muted',
                'focus:outline-none focus:border-synapse',
                'transition-colors duration-200'
              )}
            />
          </div>

          {/* Type filter */}
          <div className="flex items-center gap-2">
            <Filter className="w-4 h-4 text-text-muted" />
            <select
              value={filterType}
              onChange={(e) => setFilterType(e.target.value as AssetType | 'all')}
              className={clsx(
                'px-3 py-1.5 rounded-lg text-sm',
                'bg-slate-dark border border-slate-mid',
                'text-text-secondary',
                'focus:outline-none focus:border-synapse'
              )}
            >
              <option value="all">{t('pack.modals.editDeps.allTypes')}</option>
              {availableTypes.map((type) => (
                <option key={type} value={type}>
                  {type}
                </option>
              ))}
            </select>
          </div>
        </div>

        {/* Content */}
        <div className="flex-1 overflow-y-auto p-6">
          {/* Dependencies list */}
          {filteredDependencies.length > 0 ? (
            <div className="space-y-3 mb-6">
              {filteredDependencies.map((dep, index) => (
                <DependencyItem
                  key={dep.name}
                  dependency={dep}
                  isExpanded={expandedIndex === index}
                  isMarkedForRemoval={removedNames.has(dep.name)}
                  onToggleExpand={() => setExpandedIndex(expandedIndex === index ? null : index)}
                  onRemove={() => handleRemove(dep.name)}
                  onRestore={() => handleRestore(dep.name)}
                />
              ))}
            </div>
          ) : (
            <div className="text-center py-8 text-text-muted mb-6">
              {searchQuery || filterType !== 'all'
                ? t('pack.modals.editDeps.noMatch')
                : t('pack.modals.editDeps.noDeps')}
            </div>
          )}

          {/* Add dependency panel */}
          <AddDependencyPanel onAdd={handleAdd} onSearch={onSearch} />
        </div>

        {/* Footer */}
        <div className="flex justify-end gap-3 p-6 border-t border-slate-mid/50">
          <Button variant="secondary" onClick={onClose}>
            {t('common.cancel')}
          </Button>
          <Button
            variant="primary"
            disabled={!hasChanges || isSaving}
            onClick={handleSave}
          >
            {isSaving ? (
              <Loader2 className="w-4 h-4 animate-spin" />
            ) : null}
            {t('pack.modals.editDeps.saveChanges')}
          </Button>
        </div>
      </div>
    </div>
  )
}

export default EditDependenciesModal
