/**
 * SearchFilters - Floating Chips Component
 *
 * Phase 5: Premium filter UI for BrowsePage with animated chips.
 * Features:
 * - Color-coded provider chips (tRPC=purple, REST=blue, Archive=amber)
 * - Glowing status indicators with proper visibility
 * - Two-step filter selection: first type, then values
 * - Multi-select support for Model Type filter
 * - Active filter chips with remove button
 * - "Clear all" when multiple filters active
 * - Loading/Fetching/Offline states
 */

import { useState, useEffect, useRef, createContext, useContext, useCallback } from 'react'
import { useTranslation } from 'react-i18next'
import {
  Zap,
  Globe,
  Archive,
  ChevronDown,
  ChevronRight,
  X,
  Plus,
  Loader2,
  Trash2,
  AlertTriangle,
  Check,
  Filter,
} from 'lucide-react'
import { clsx } from 'clsx'
import type { SearchProvider, SortOption, PeriodOption } from '@/lib/api/searchTypes'
import {
  PROVIDER_CONFIGS,
  SORT_OPTIONS,
  PERIOD_OPTIONS,
  BASE_MODEL_OPTIONS,
  MODEL_TYPE_OPTIONS,
  FILE_FORMAT_OPTIONS,
  CATEGORY_OPTIONS,
} from '@/lib/api/searchTypes'
import { isProviderAvailable } from '@/lib/api/searchAdapters'

// =============================================================================
// Types
// =============================================================================

export type FilterType = 'baseModel' | 'modelTypes' | 'fileFormat' | 'category'

interface SearchFiltersProps {
  provider: SearchProvider
  onProviderChange: (provider: SearchProvider) => void
  sortBy: SortOption
  onSortChange: (sort: SortOption) => void
  period: PeriodOption
  onPeriodChange: (period: PeriodOption) => void
  // Single-select filters
  baseModel: string
  onBaseModelChange: (model: string) => void
  fileFormat?: string
  onFileFormatChange?: (format: string) => void
  category?: string
  onCategoryChange?: (category: string) => void
  // Multi-select filter
  modelTypes?: string[]
  onModelTypesChange?: (types: string[]) => void
  // Legacy single-select (backwards compatibility)
  modelType?: string
  onModelTypeChange?: (type: string) => void
  // State
  isLoading?: boolean
  isError?: boolean
  disabled?: boolean
}

// =============================================================================
// Filter Type Configuration
// =============================================================================

interface FilterTypeConfig {
  key: FilterType
  labelKey: string
  icon: React.ReactNode
  multiSelect: boolean
  options: readonly { value: string; label: string }[]
}

const FILTER_TYPE_CONFIGS: FilterTypeConfig[] = [
  {
    key: 'baseModel',
    labelKey: 'filterBaseModel',
    icon: <Filter className="w-4 h-4" />,
    multiSelect: false,
    options: BASE_MODEL_OPTIONS,
  },
  {
    key: 'modelTypes',
    labelKey: 'filterModelType',
    icon: <Filter className="w-4 h-4" />,
    multiSelect: true,
    options: MODEL_TYPE_OPTIONS,
  },
  {
    key: 'fileFormat',
    labelKey: 'filterFileFormat',
    icon: <Filter className="w-4 h-4" />,
    multiSelect: false,
    options: FILE_FORMAT_OPTIONS,
  },
  {
    key: 'category',
    labelKey: 'filterCategory',
    icon: <Filter className="w-4 h-4" />,
    multiSelect: false,
    options: CATEGORY_OPTIONS,
  },
]

// =============================================================================
// Provider Color Schemes - Fixed tRPC visibility
// =============================================================================

const PROVIDER_COLORS = {
  trpc: {
    chip: 'bg-gradient-to-r from-violet-500/25 to-fuchsia-500/25 border-violet-400/60 text-violet-300',
    chipHover: 'hover:border-violet-400/80 hover:shadow-lg hover:shadow-violet-500/40',
    dot: 'bg-violet-400',
    dotGlow: '0 0 12px rgba(167, 139, 250, 1), 0 0 20px rgba(167, 139, 250, 0.6)',
    status: 'bg-emerald-500/15 border-emerald-400/40 text-emerald-400',
    statusDot: 'bg-emerald-400',
    statusDotGlow: '0 0 10px rgba(52, 211, 153, 0.8)',
  },
  rest: {
    chip: 'bg-gradient-to-r from-blue-500/25 to-cyan-500/25 border-blue-400/60 text-blue-300',
    chipHover: 'hover:border-blue-400/80 hover:shadow-lg hover:shadow-blue-500/40',
    dot: 'bg-blue-400',
    dotGlow: '0 0 12px rgba(96, 165, 250, 1), 0 0 20px rgba(96, 165, 250, 0.6)',
    status: 'bg-blue-500/15 border-blue-400/40 text-blue-400',
    statusDot: 'bg-blue-400',
    statusDotGlow: '0 0 10px rgba(96, 165, 250, 0.8)',
  },
  archive: {
    chip: 'bg-gradient-to-r from-amber-500/25 to-orange-500/25 border-amber-400/60 text-amber-300',
    chipHover: 'hover:border-amber-400/80 hover:shadow-lg hover:shadow-amber-500/40',
    dot: 'bg-amber-400',
    dotGlow: '0 0 12px rgba(251, 191, 36, 1), 0 0 20px rgba(251, 191, 36, 0.6)',
    status: 'bg-amber-500/15 border-amber-400/40 text-amber-400',
    statusDot: 'bg-amber-400',
    statusDotGlow: '0 0 10px rgba(251, 191, 36, 0.8)',
  },
}

// =============================================================================
// Dropdown Context & Components
// =============================================================================

const DropdownContext = createContext<{ close: () => void } | null>(null)

interface DropdownProps {
  trigger: React.ReactNode
  children: React.ReactNode
  align?: 'left' | 'center' | 'right'
  maxHeight?: string
  open?: boolean
  onOpenChange?: (open: boolean) => void
}

function Dropdown({
  trigger,
  children,
  align = 'center',
  maxHeight = '300px',
  open: controlledOpen,
  onOpenChange,
}: DropdownProps) {
  const [internalOpen, setInternalOpen] = useState(false)
  const dropdownRef = useRef<HTMLDivElement>(null)

  const isControlled = controlledOpen !== undefined
  const isOpen = isControlled ? controlledOpen : internalOpen
  const setIsOpen = isControlled ? (onOpenChange ?? (() => {})) : setInternalOpen

  useEffect(() => {
    function handleClickOutside(event: MouseEvent) {
      if (dropdownRef.current && !dropdownRef.current.contains(event.target as Node)) {
        setIsOpen(false)
      }
    }
    document.addEventListener('mousedown', handleClickOutside)
    return () => document.removeEventListener('mousedown', handleClickOutside)
  }, [setIsOpen])

  const alignClass = {
    left: 'left-0',
    center: 'left-1/2 -translate-x-1/2',
    right: 'right-0',
  }[align]

  const close = useCallback(() => setIsOpen(false), [setIsOpen])

  return (
    <div className="relative" ref={dropdownRef}>
      <div onClick={() => setIsOpen(!isOpen)}>{trigger}</div>
      {isOpen && (
        <DropdownContext.Provider value={{ close }}>
          <div
            className={clsx(
              'absolute top-full mt-2 min-w-[220px] p-1.5',
              'bg-slate-darker/95 backdrop-blur-xl',
              'border border-slate-mid/30 rounded-xl',
              'shadow-xl shadow-black/30',
              'animate-in fade-in slide-in-from-top-2 duration-150',
              'z-[9999] overflow-y-auto',
              alignClass
            )}
            style={{ maxHeight }}
          >
            {children}
          </div>
        </DropdownContext.Provider>
      )}
    </div>
  )
}

interface DropdownItemProps {
  children: React.ReactNode
  selected?: boolean
  disabled?: boolean
  onClick: () => void
  closeOnClick?: boolean
}

function DropdownItem({
  children,
  selected,
  disabled,
  onClick,
  closeOnClick = true,
}: DropdownItemProps) {
  const dropdown = useContext(DropdownContext)

  const handleClick = () => {
    if (disabled) return
    onClick()
    if (closeOnClick) {
      dropdown?.close()
    }
  }

  return (
    <button
      onClick={handleClick}
      disabled={disabled}
      className={clsx(
        'w-full flex items-center gap-3 px-3 py-2 rounded-lg text-sm text-left',
        'transition-colors duration-150',
        disabled && 'opacity-40 cursor-not-allowed',
        selected
          ? 'bg-synapse/20 text-synapse'
          : 'text-text-secondary hover:bg-slate-mid/50 hover:text-text-primary'
      )}
    >
      {children}
    </button>
  )
}

interface CheckboxItemProps {
  children: React.ReactNode
  checked: boolean
  onChange: (checked: boolean) => void
}

function CheckboxItem({ children, checked, onChange }: CheckboxItemProps) {
  return (
    <button
      onClick={() => onChange(!checked)}
      className={clsx(
        'w-full flex items-center gap-3 px-3 py-2 rounded-lg text-sm text-left',
        'transition-colors duration-150',
        checked
          ? 'bg-synapse/20 text-synapse'
          : 'text-text-secondary hover:bg-slate-mid/50 hover:text-text-primary'
      )}
    >
      <div
        className={clsx(
          'w-4 h-4 rounded border-2 flex items-center justify-center transition-colors',
          checked ? 'bg-synapse border-synapse' : 'border-slate-mid bg-transparent'
        )}
      >
        {checked && <Check className="w-3 h-3 text-white" />}
      </div>
      {children}
    </button>
  )
}

// DropdownDivider kept for potential future use
// function DropdownDivider() {
//   return <div className="h-px bg-slate-mid/30 my-1 mx-2" />
// }

function DropdownLabel({ children }: { children: React.ReactNode }) {
  return (
    <div className="px-3 py-2 text-xs text-text-muted uppercase tracking-wider font-medium sticky top-0 bg-slate-darker/95">
      {children}
    </div>
  )
}

// =============================================================================
// Chip Components
// =============================================================================

interface ChipProps {
  children: React.ReactNode
  variant?: 'provider' | 'filter' | 'active' | 'add' | 'clear'
  onClick?: () => void
  className?: string
  loading?: boolean
}

function Chip({ children, variant = 'filter', onClick, className, loading }: ChipProps) {
  const baseClasses = clsx(
    'inline-flex items-center gap-2 px-4 py-2 rounded-full text-sm font-medium',
    'cursor-pointer select-none transition-all duration-200',
    'active:scale-[0.97]',
    loading && 'pointer-events-none'
  )

  const variantClasses = {
    provider: '', // Custom per provider
    filter: clsx(
      'bg-slate-dark/80 border border-slate-mid/50',
      'text-text-secondary',
      'hover:border-slate-light/60 hover:text-text-primary',
      'hover:-translate-y-0.5 hover:shadow-md'
    ),
    active: clsx(
      'bg-synapse/15 border border-synapse/40',
      'text-synapse',
      'hover:bg-synapse/25',
      'group'
    ),
    add: clsx(
      'bg-transparent border border-dashed border-slate-mid/50',
      'text-text-muted',
      'hover:border-synapse/40 hover:text-synapse hover:border-solid'
    ),
    clear: clsx(
      'bg-transparent border border-dashed border-red-500/30',
      'text-red-400/70',
      'hover:border-red-500/50 hover:text-red-400 hover:border-solid hover:bg-red-500/10'
    ),
  }

  return (
    <button onClick={onClick} className={clsx(baseClasses, variantClasses[variant], className)}>
      {loading && <Loader2 className="w-4 h-4 animate-spin" />}
      {children}
    </button>
  )
}

// =============================================================================
// Status Badge
// =============================================================================

interface StatusBadgeProps {
  provider: SearchProvider
  isLoading?: boolean
  isError?: boolean
}

function StatusBadge({ provider, isLoading, isError }: StatusBadgeProps) {
  const { t } = useTranslation()
  const colors = PROVIDER_COLORS[provider]
  const config = PROVIDER_CONFIGS[provider]

  if (isError) {
    return (
      <div className="flex items-center gap-2 px-3 py-1.5 rounded-full bg-red-500/15 border border-red-400/40">
        <AlertTriangle className="w-3 h-3 text-red-400" />
        <span className="text-xs text-red-400 font-semibold uppercase tracking-wide">{t('searchFilters.offline')}</span>
      </div>
    )
  }

  if (isLoading) {
    return (
      <div className={clsx('flex items-center gap-2 px-3 py-1.5 rounded-full border', colors.status)}>
        <Loader2 className="w-3 h-3 animate-spin" />
        <span className="text-xs font-semibold uppercase tracking-wide">{t('searchFilters.fetching')}</span>
      </div>
    )
  }

  return (
    <div className={clsx('flex items-center gap-2 px-3 py-1.5 rounded-full border', colors.status)}>
      <span
        className={clsx('w-2 h-2 rounded-full', colors.statusDot)}
        style={{
          boxShadow: colors.statusDotGlow,
          animation: 'glow-pulse 2s ease-in-out infinite',
        }}
      />
      <span className="text-xs font-semibold uppercase tracking-wide">{config.statusLabel}</span>
    </div>
  )
}

// =============================================================================
// Filter Value Selector (Second Step)
// =============================================================================

interface FilterValueSelectorProps {
  filterType: FilterTypeConfig
  selectedValues: string[]
  onChange: (values: string[]) => void
  onClose: () => void
}

function FilterValueSelector({
  filterType,
  selectedValues,
  onChange,
  onClose,
}: FilterValueSelectorProps) {
  const { t } = useTranslation()
  const dropdownRef = useRef<HTMLDivElement>(null)
  const [searchTerm, setSearchTerm] = useState('')

  useEffect(() => {
    function handleClickOutside(event: MouseEvent) {
      if (dropdownRef.current && !dropdownRef.current.contains(event.target as Node)) {
        onClose()
      }
    }
    document.addEventListener('mousedown', handleClickOutside)
    return () => document.removeEventListener('mousedown', handleClickOutside)
  }, [onClose])

  const filteredOptions = filterType.options.filter(
    (opt) =>
      opt.value && opt.label.toLowerCase().includes(searchTerm.toLowerCase())
  )

  const handleToggle = (value: string) => {
    if (filterType.multiSelect) {
      if (selectedValues.includes(value)) {
        onChange(selectedValues.filter((v) => v !== value))
      } else {
        onChange([...selectedValues, value])
      }
    } else {
      onChange([value])
      onClose()
    }
  }

  return (
    <div
      ref={dropdownRef}
      className={clsx(
        'absolute top-full mt-2 left-0 min-w-[280px] p-1.5',
        'bg-slate-darker/95 backdrop-blur-xl',
        'border border-slate-mid/30 rounded-xl',
        'shadow-xl shadow-black/30',
        'animate-in fade-in slide-in-from-top-2 duration-150',
        'z-[10000]'
      )}
    >
      {/* Header */}
      <div className="flex items-center justify-between px-3 py-2 border-b border-slate-mid/30 mb-1">
        <span className="text-sm font-medium text-text-primary">{t('searchFilters.' + filterType.labelKey)}</span>
        {filterType.multiSelect && selectedValues.length > 0 && (
          <span className="text-xs text-synapse">{t('searchFilters.selected', { count: selectedValues.length })}</span>
        )}
      </div>

      {/* Search (for large lists) */}
      {filterType.options.length > 10 && (
        <div className="px-2 pb-2">
          <input
            type="text"
            placeholder={t('searchFilters.search', { label: t('searchFilters.' + filterType.labelKey).toLowerCase() })}
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            className={clsx(
              'w-full px-3 py-2 text-sm rounded-lg',
              'bg-slate-dark/80 border border-slate-mid/50',
              'text-text-primary placeholder-text-muted',
              'focus:outline-none focus:border-synapse/50'
            )}
            autoFocus
          />
        </div>
      )}

      {/* Options */}
      <div className="max-h-[300px] overflow-y-auto">
        {filteredOptions.length === 0 ? (
          <div className="px-3 py-4 text-sm text-text-muted text-center">{t('searchFilters.noOptions')}</div>
        ) : (
          filteredOptions.map((opt) =>
            filterType.multiSelect ? (
              <CheckboxItem
                key={opt.value}
                checked={selectedValues.includes(opt.value)}
                onChange={() => handleToggle(opt.value)}
              >
                {opt.label}
              </CheckboxItem>
            ) : (
              <DropdownItem
                key={opt.value}
                selected={selectedValues.includes(opt.value)}
                onClick={() => handleToggle(opt.value)}
              >
                {opt.label}
                {selectedValues.includes(opt.value) && (
                  <Check className="w-4 h-4 ml-auto flex-shrink-0" />
                )}
              </DropdownItem>
            )
          )
        )}
      </div>

      {/* Done button for multi-select */}
      {filterType.multiSelect && (
        <div className="px-2 pt-2 border-t border-slate-mid/30 mt-1">
          <button
            onClick={onClose}
            className={clsx(
              'w-full px-4 py-2 rounded-lg text-sm font-medium',
              'bg-synapse/20 text-synapse',
              'hover:bg-synapse/30 transition-colors'
            )}
          >
            {t('searchFilters.done')}
          </button>
        </div>
      )}
    </div>
  )
}

// =============================================================================
// Add Filter Button with Two-Step Selection
// =============================================================================

interface AddFilterButtonProps {
  availableFilters: FilterTypeConfig[]
  getSelectedValues: (filterType: FilterType) => string[]
  onValuesChange: (filterType: FilterType, values: string[]) => void
}

function AddFilterButton({
  availableFilters,
  getSelectedValues,
  onValuesChange,
}: AddFilterButtonProps) {
  const { t } = useTranslation()
  const [isOpen, setIsOpen] = useState(false)
  const [selectedFilterType, setSelectedFilterType] = useState<FilterTypeConfig | null>(null)
  const containerRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    function handleClickOutside(event: MouseEvent) {
      if (containerRef.current && !containerRef.current.contains(event.target as Node)) {
        setIsOpen(false)
        setSelectedFilterType(null)
      }
    }
    document.addEventListener('mousedown', handleClickOutside)
    return () => document.removeEventListener('mousedown', handleClickOutside)
  }, [])

  const handleFilterTypeSelect = (config: FilterTypeConfig) => {
    setSelectedFilterType(config)
  }

  const handleValuesChange = (values: string[]) => {
    if (selectedFilterType) {
      onValuesChange(selectedFilterType.key, values)
    }
  }

  const handleClose = () => {
    setSelectedFilterType(null)
    setIsOpen(false)
  }

  if (availableFilters.length === 0) return null

  return (
    <div className="relative" ref={containerRef}>
      <Chip variant="add" onClick={() => setIsOpen(!isOpen)}>
        <Plus className="w-4 h-4" />
        <span>{t('searchFilters.addFilter')}</span>
      </Chip>

      {/* Step 1: Filter Type Selection */}
      {isOpen && !selectedFilterType && (
        <div
          className={clsx(
            'absolute top-full mt-2 left-0 min-w-[200px] p-1.5',
            'bg-slate-darker/95 backdrop-blur-xl',
            'border border-slate-mid/30 rounded-xl',
            'shadow-xl shadow-black/30',
            'animate-in fade-in slide-in-from-top-2 duration-150',
            'z-[9999]'
          )}
        >
          <DropdownLabel>{t('searchFilters.selectFilterType')}</DropdownLabel>
          {availableFilters.map((config) => (
            <button
              key={config.key}
              onClick={() => handleFilterTypeSelect(config)}
              className={clsx(
                'w-full flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm text-left',
                'transition-colors duration-150',
                'text-text-secondary hover:bg-slate-mid/50 hover:text-text-primary'
              )}
            >
              {config.icon}
              <span className="flex-1">{t('searchFilters.' + config.labelKey)}</span>
              {config.multiSelect && (
                <span className="text-xs text-text-muted bg-slate-mid/30 px-1.5 py-0.5 rounded">
                  {t('searchFilters.multi')}
                </span>
              )}
              <ChevronRight className="w-4 h-4 opacity-50" />
            </button>
          ))}
        </div>
      )}

      {/* Step 2: Value Selection */}
      {isOpen && selectedFilterType && (
        <FilterValueSelector
          filterType={selectedFilterType}
          selectedValues={getSelectedValues(selectedFilterType.key)}
          onChange={handleValuesChange}
          onClose={handleClose}
        />
      )}
    </div>
  )
}

// =============================================================================
// Main Component
// =============================================================================

export function SearchFilters({
  provider,
  onProviderChange,
  sortBy,
  onSortChange,
  period,
  onPeriodChange,
  baseModel,
  onBaseModelChange,
  modelTypes,
  onModelTypesChange,
  modelType,
  onModelTypeChange,
  fileFormat,
  onFileFormatChange,
  category,
  onCategoryChange,
  isLoading,
  isError,
  disabled,
}: SearchFiltersProps) {
  const { t } = useTranslation()
  const config = PROVIDER_CONFIGS[provider]
  const colors = PROVIDER_COLORS[provider]
  const trpcAvailable = isProviderAvailable('trpc')

  // Handle both multi-select and legacy single-select for model type
  const effectiveModelTypes = modelTypes ?? (modelType ? [modelType] : [])
  const handleModelTypesChange = useCallback(
    (types: string[]) => {
      if (onModelTypesChange) {
        onModelTypesChange(types)
      } else if (onModelTypeChange) {
        // Fallback to legacy single-select (use first value)
        onModelTypeChange(types[0] || '')
      }
    },
    [onModelTypesChange, onModelTypeChange]
  )

  // Get selected values for a filter type
  const getSelectedValues = useCallback(
    (filterType: FilterType): string[] => {
      switch (filterType) {
        case 'baseModel':
          return baseModel ? [baseModel] : []
        case 'modelTypes':
          return effectiveModelTypes
        case 'fileFormat':
          return fileFormat ? [fileFormat] : []
        case 'category':
          return category ? [category] : []
        default:
          return []
      }
    },
    [baseModel, effectiveModelTypes, fileFormat, category]
  )

  // Handle value changes for any filter type
  const handleValuesChange = useCallback(
    (filterType: FilterType, values: string[]) => {
      switch (filterType) {
        case 'baseModel':
          onBaseModelChange(values[0] || '')
          break
        case 'modelTypes':
          handleModelTypesChange(values)
          break
        case 'fileFormat':
          onFileFormatChange?.(values[0] || '')
          break
        case 'category':
          onCategoryChange?.(values[0] || '')
          break
      }
    },
    [onBaseModelChange, handleModelTypesChange, onFileFormatChange, onCategoryChange]
  )

  // Determine which filters can be added
  // Multi-select filters (modelTypes) are always available to add more
  // Single-select filters disappear once a value is selected
  const availableFilters = FILTER_TYPE_CONFIGS.filter((config) => {
    switch (config.key) {
      case 'baseModel':
        return !baseModel
      case 'modelTypes':
        // Always show for multi-select - user can add more types
        return onModelTypesChange || onModelTypeChange
      case 'fileFormat':
        return onFileFormatChange && !fileFormat
      case 'category':
        return onCategoryChange && !category
      default:
        return false
    }
  })

  // Count active filters (non-default values)
  const activeFilterCount = [
    sortBy !== 'Most Downloaded' ? 1 : 0,
    period !== 'AllTime' ? 1 : 0,
    baseModel ? 1 : 0,
    effectiveModelTypes.length > 0 ? effectiveModelTypes.length : 0,
    fileFormat ? 1 : 0,
    category ? 1 : 0,
  ].reduce((a, b) => a + b, 0)

  const handleClearAll = () => {
    onSortChange('Most Downloaded')
    onPeriodChange('AllTime')
    onBaseModelChange('')
    handleModelTypesChange([])
    onFileFormatChange?.('')
    onCategoryChange?.('')
  }

  return (
    <div
      className={clsx(
        'relative z-50',
        'flex items-center gap-2.5 flex-wrap p-3',
        'bg-slate-dark/40 backdrop-blur-sm rounded-2xl',
        'border border-slate-mid/30',
        disabled && 'opacity-50 pointer-events-none'
      )}
    >
      {/* Provider Chip */}
      <Dropdown
        trigger={
          <Chip
            variant="provider"
            loading={isLoading}
            className={clsx('border', colors.chip, colors.chipHover, 'hover:-translate-y-0.5')}
          >
            {!isLoading && (
              <span
                className={clsx('w-2.5 h-2.5 rounded-full', colors.dot)}
                style={{
                  boxShadow: colors.dotGlow,
                  animation: 'glow-pulse 2s ease-in-out infinite',
                }}
              />
            )}
            <span>{config.shortName}</span>
            <ChevronDown className="w-4 h-4 opacity-60" />
          </Chip>
        }
      >
        <DropdownItem
          selected={provider === 'trpc'}
          disabled={!trpcAvailable}
          onClick={() => trpcAvailable && onProviderChange('trpc')}
        >
          <Zap className="w-4 h-4 text-violet-400" />
          <span>{t('searchFilters.providerTrpc')}</span>
          {!trpcAvailable && <span className="ml-auto text-xs text-red-400">{t('searchFilters.offline')}</span>}
        </DropdownItem>
        <DropdownItem selected={provider === 'rest'} onClick={() => onProviderChange('rest')}>
          <Globe className="w-4 h-4 text-blue-400" />
          <span>{t('searchFilters.providerRest')}</span>
        </DropdownItem>
        <DropdownItem selected={provider === 'archive'} onClick={() => onProviderChange('archive')}>
          <Archive className="w-4 h-4 text-amber-400" />
          <span>{t('searchFilters.providerArchive')}</span>
        </DropdownItem>
      </Dropdown>

      {/* Divider */}
      <span className="w-1 h-1 rounded-full bg-slate-mid/50" />

      {/* Sort - Show as active chip if not default */}
      {sortBy !== 'Most Downloaded' ? (
        <Chip variant="active" onClick={() => onSortChange('Most Downloaded')}>
          <span>{sortBy}</span>
          <X className="w-4 h-4 opacity-60 group-hover:opacity-100 transition-opacity" />
        </Chip>
      ) : (
        <Dropdown
          trigger={
            <Chip variant="filter">
              <span>{t('searchFilters.defaultSort')}</span>
              <ChevronDown className="w-4 h-4 opacity-50" />
            </Chip>
          }
        >
          {SORT_OPTIONS.map((opt) => (
            <DropdownItem
              key={opt.value}
              selected={sortBy === opt.value}
              onClick={() => onSortChange(opt.value as SortOption)}
            >
              {opt.label}
            </DropdownItem>
          ))}
        </Dropdown>
      )}

      {/* Period - Show as active chip if not default */}
      {period !== 'AllTime' ? (
        <Chip variant="active" onClick={() => onPeriodChange('AllTime')}>
          <span>{PERIOD_OPTIONS.find((p) => p.value === period)?.label}</span>
          <X className="w-4 h-4 opacity-60 group-hover:opacity-100 transition-opacity" />
        </Chip>
      ) : (
        <Dropdown
          trigger={
            <Chip variant="filter">
              <span>{t('searchFilters.defaultPeriod')}</span>
              <ChevronDown className="w-4 h-4 opacity-50" />
            </Chip>
          }
        >
          {PERIOD_OPTIONS.map((opt) => (
            <DropdownItem
              key={opt.value}
              selected={period === opt.value}
              onClick={() => onPeriodChange(opt.value as PeriodOption)}
            >
              {opt.label}
            </DropdownItem>
          ))}
        </Dropdown>
      )}

      {/* Active filter chips */}
      {baseModel && (
        <Chip variant="active" onClick={() => onBaseModelChange('')}>
          <span>{BASE_MODEL_OPTIONS.find((m) => m.value === baseModel)?.label || baseModel}</span>
          <X className="w-4 h-4 opacity-60 group-hover:opacity-100 transition-opacity" />
        </Chip>
      )}

      {/* Model Types - show each as separate chip */}
      {effectiveModelTypes.map((type) => (
        <Chip
          key={type}
          variant="active"
          onClick={() => handleModelTypesChange(effectiveModelTypes.filter((t) => t !== type))}
        >
          <span>{MODEL_TYPE_OPTIONS.find((t) => t.value === type)?.label || type}</span>
          <X className="w-4 h-4 opacity-60 group-hover:opacity-100 transition-opacity" />
        </Chip>
      ))}

      {fileFormat && onFileFormatChange && (
        <Chip variant="active" onClick={() => onFileFormatChange('')}>
          <span>{FILE_FORMAT_OPTIONS.find((f) => f.value === fileFormat)?.label || fileFormat}</span>
          <X className="w-4 h-4 opacity-60 group-hover:opacity-100 transition-opacity" />
        </Chip>
      )}

      {category && onCategoryChange && (
        <Chip variant="active" onClick={() => onCategoryChange('')}>
          <span>{CATEGORY_OPTIONS.find((c) => c.value === category)?.label || category}</span>
          <X className="w-4 h-4 opacity-60 group-hover:opacity-100 transition-opacity" />
        </Chip>
      )}

      {/* Add Filter Button - Two-step selection */}
      <AddFilterButton
        availableFilters={availableFilters}
        getSelectedValues={getSelectedValues}
        onValuesChange={handleValuesChange}
      />

      {/* Clear All - Show when 2+ filters active */}
      {activeFilterCount >= 2 && (
        <Chip variant="clear" onClick={handleClearAll}>
          <Trash2 className="w-4 h-4" />
          <span>{t('searchFilters.clearAll')}</span>
        </Chip>
      )}

      {/* Spacer */}
      <div className="flex-1" />

      {/* Status Badge */}
      <StatusBadge provider={provider} isLoading={isLoading} isError={isError} />
    </div>
  )
}
